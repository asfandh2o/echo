from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update, desc, func
from typing import List
from uuid import UUID
from db.session import get_db
from models.user import User
from models.notification import Notification
from schemas.notification import NotificationResponse, NotificationActionRequest, WebhookBatchRequest
from api.deps import get_current_user
from core.config import settings
from core.logging import get_logger

router = APIRouter(prefix="/notifications", tags=["notifications"])
logger = get_logger(__name__)


@router.get("/", response_model=List[NotificationResponse])
async def list_notifications(
    unread_only: bool = False,
    limit: int = 30,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """List notifications for the current user."""
    query = select(Notification).where(
        Notification.user_id == current_user.id
    ).order_by(desc(Notification.created_at)).limit(limit)

    if unread_only:
        query = query.where(Notification.read == False)

    result = await db.execute(query)
    notifications = result.scalars().all()
    return [NotificationResponse.from_model(n) for n in notifications]


@router.get("/unread-count")
async def unread_count(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Get count of unread notifications."""
    result = await db.execute(
        select(func.count(Notification.id)).where(
            Notification.user_id == current_user.id,
            Notification.read == False,
        )
    )
    count = result.scalar()
    return {"count": count}


@router.patch("/{notification_id}/read")
async def mark_read(
    notification_id: UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Mark a notification as read."""
    result = await db.execute(
        select(Notification).where(
            Notification.id == notification_id,
            Notification.user_id == current_user.id,
        )
    )
    notif = result.scalar_one_or_none()
    if not notif:
        raise HTTPException(status_code=404, detail="Notification not found")

    notif.read = True
    await db.commit()
    return {"status": "ok"}


@router.patch("/read-all")
async def mark_all_read(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Mark all notifications as read."""
    await db.execute(
        update(Notification).where(
            Notification.user_id == current_user.id,
            Notification.read == False,
        ).values(read=True)
    )
    await db.commit()
    return {"status": "ok"}


@router.post("/{notification_id}/action")
async def execute_notification_action(
    notification_id: UUID,
    body: NotificationActionRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Execute an action on an interactive notification (confirm/dismiss)."""
    result = await db.execute(
        select(Notification).where(
            Notification.id == notification_id,
            Notification.user_id == current_user.id,
        )
    )
    notif = result.scalar_one_or_none()
    if not notif:
        raise HTTPException(status_code=404, detail="Notification not found")

    if not notif.action_type:
        raise HTTPException(status_code=400, detail="This notification has no action")

    if notif.action_status and notif.action_status != "pending":
        raise HTTPException(status_code=400, detail=f"Action already {notif.action_status}")

    if body.action == "confirm":
        if notif.action_type == "confirm_meeting":
            from tools.calendar_tool import CalendarTool
            from models.calendar_event import CalendarEvent

            payload = notif.action_payload or {}

            calendar_tool = CalendarTool(current_user.encrypted_oauth_tokens, str(current_user.id))
            google_event = await calendar_tool.create_event(
                summary=payload.get("summary", "Meeting"),
                start_time=payload.get("start_time"),
                end_time=payload.get("end_time"),
                attendees=payload.get("attendees", []),
                description=payload.get("description"),
                location=payload.get("location"),
            )

            calendar_event = CalendarEvent(
                user_id=current_user.id,
                email_id=payload.get("email_id"),
                google_event_id=google_event["id"],
                summary=payload.get("summary", "Meeting"),
                start_time=payload["start_time"],
                end_time=payload["end_time"],
                attendees=payload.get("attendees", []),
                location=payload.get("location"),
                status="created",
                action_type="create",
                llm_extraction=payload.get("extraction", {}),
                extra_data={"html_link": google_event.get("html_link"), "source": "notification_confirm"},
            )
            db.add(calendar_event)

        notif.action_status = "confirmed"
        notif.read = True

    elif body.action == "dismiss":
        notif.action_status = "dismissed"
        notif.read = True

    await db.commit()
    logger.info("notification_action_executed", notification_id=str(notification_id), action=body.action)
    return {"status": notif.action_status}


@router.post("/webhook")
async def receive_webhook(
    body: WebhookBatchRequest,
    db: AsyncSession = Depends(get_db),
):
    """Receive notifications from external services (HERA, etc.).
    Authenticates via API key, not JWT."""
    if body.api_key != settings.SECRET_KEY:
        raise HTTPException(status_code=401, detail="Invalid API key")

    created = 0
    for notif_data in body.notifications:
        # Look up user by email
        result = await db.execute(
            select(User).where(User.email == notif_data.email)
        )
        user = result.scalar_one_or_none()
        if not user:
            logger.warning("webhook_user_not_found", email=notif_data.email)
            continue

        notification = Notification(
            user_id=user.id,
            type=notif_data.type,
            source=notif_data.source,
            title=notif_data.title,
            message=notif_data.message,
            extra_data=notif_data.metadata,
        )
        db.add(notification)
        created += 1

        # Also create a Task for HERA task assignments
        if notif_data.type in ("task_assigned", "task_updated"):
            try:
                from services.task_service import TaskService
                task_service = TaskService(db)
                meta = notif_data.metadata or {}
                await task_service.create_task_from_hera(
                    user_id=str(user.id),
                    hera_data={
                        "title": notif_data.message or notif_data.title,
                        "description": notif_data.title,
                        "task_id": meta.get("task_id"),
                        "project_name": meta.get("project_name"),
                        "priority": meta.get("priority", "normal"),
                        "deadline": meta.get("deadline"),
                    },
                )
            except Exception as e:
                logger.warning("hera_task_creation_failed", error=str(e))

    await db.commit()
    logger.info("webhook_notifications_created", count=created)
    return {"created": created}
