from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from datetime import datetime, timedelta
from db.session import get_db
from models.user import User
from models.email import Email
from models.suggestion import Suggestion
from models.notification import Notification
from models.calendar_event import CalendarEvent
from models.task import Task
from core.config import settings
from core.logging import get_logger

router = APIRouter(prefix="/metrics", tags=["metrics"])
logger = get_logger(__name__)


@router.get("/activity")
async def get_activity_metrics(
    api_key: str = Query(...),
    days: int = Query(7),
    db: AsyncSession = Depends(get_db),
):
    """Activity metrics for ARGUS. API key auth."""
    if api_key != settings.SECRET_KEY:
        raise HTTPException(status_code=401, detail="Invalid API key")

    since = datetime.utcnow() - timedelta(days=days)

    users = (await db.execute(select(User))).scalars().all()

    results = []
    for user in users:
        uid = user.id

        # Email count
        email_count = (await db.execute(
            select(func.count(Email.id)).where(
                Email.user_id == uid, Email.received_at >= since
            )
        )).scalar() or 0

        # Suggestion stats
        suggestions = (await db.execute(
            select(Suggestion).where(
                Suggestion.user_id == uid, Suggestion.created_at >= since
            )
        )).scalars().all()

        suggestion_total = len(suggestions)
        accepted = len([s for s in suggestions if s.feedback_type == "accepted"])
        rejected = len([s for s in suggestions if s.feedback_type == "rejected"])
        edited = len([s for s in suggestions if s.feedback_type == "edited"])

        # Calendar events and meeting hours
        cal_events = (await db.execute(
            select(CalendarEvent).where(
                CalendarEvent.user_id == uid, CalendarEvent.created_at >= since
            )
        )).scalars().all()

        meeting_hours = 0.0
        for ev in cal_events:
            if ev.start_time and ev.end_time:
                diff = (ev.end_time - ev.start_time).total_seconds() / 3600
                meeting_hours += diff

        # Notification stats
        notifs = (await db.execute(
            select(Notification).where(
                Notification.user_id == uid, Notification.created_at >= since
            )
        )).scalars().all()

        notif_total = len(notifs)
        notif_read = len([n for n in notifs if n.read])
        notif_actioned = len([n for n in notifs if n.action_status and n.action_status != "pending"])

        # Task completion from ECHO side
        tasks = (await db.execute(
            select(Task).where(
                Task.user_id == uid, Task.created_at >= since
            )
        )).scalars().all()
        tasks_completed = len([t for t in tasks if t.status == "completed"])

        results.append({
            "user_email": user.email,
            "period_days": days,
            "emails_received": email_count,
            "suggestions_total": suggestion_total,
            "suggestions_accepted": accepted,
            "suggestions_rejected": rejected,
            "suggestions_edited": edited,
            "calendar_events": len(cal_events),
            "meeting_hours": round(meeting_hours, 1),
            "notifications_total": notif_total,
            "notifications_read": notif_read,
            "notifications_actioned": notif_actioned,
            "tasks_completed": tasks_completed,
            "tasks_total": len(tasks),
        })

    logger.info("activity_metrics_served", user_count=len(results))
    return {"metrics": results, "collected_at": datetime.utcnow().isoformat()}
