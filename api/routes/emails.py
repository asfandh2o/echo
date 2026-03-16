from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, desc
from typing import List
from db.session import get_db
from models.user import User
from models.email import Email
from schemas.email import EmailResponse
from api.deps import get_current_user
from services.gmail_service import GmailService
from services.classification_service import ClassificationService
from services.calendar_service import CalendarService
from services.suggestion_service import SuggestionService
from services.contact_service import ContactService
from services.task_service import TaskService
from models.notification import Notification
from core.logging import get_logger
from uuid import UUID

router = APIRouter(prefix="/emails", tags=["emails"])
logger = get_logger(__name__)

MEETING_KEYWORDS = ["meeting", "schedule", "calendar", "reschedule", "appointment", "call", "sync", "standup"]


@router.post("/fetch", summary="Manually fetch latest emails from Gmail")
async def fetch_emails(
    max_results: int = 20,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    gmail_service = GmailService(current_user.encrypted_oauth_tokens)
    email_data_list = await gmail_service.fetch_recent_emails(
        max_results=max_results, query="newer_than:1d"
    )

    new_count = 0
    processed = []

    for email_data in email_data_list:
        # Skip emails sent by the user themselves
        sender_field = (email_data.get("sender") or "").lower()
        user_email = (current_user.email or "").lower()
        if user_email and user_email in sender_field:
            continue

        existing = await db.execute(
            select(Email)
            .where(Email.gmail_message_id == email_data["gmail_message_id"])
            .where(Email.user_id == current_user.id)
        )
        if existing.scalar_one_or_none():
            continue

        email = Email(user_id=current_user.id, **email_data)
        db.add(email)
        await db.commit()
        await db.refresh(email)
        new_count += 1

        # Upsert contact profile for sender
        try:
            contact_service = ContactService(db)
            await contact_service.upsert_contact_from_email(email, str(current_user.id))
        except Exception as e:
            logger.warning("contact_upsert_failed", email_id=str(email.id), error=str(e))

        # --- Inline pipeline: classify → calendar/suggestion ---
        email_result = {"email_id": str(email.id), "subject": email.subject}
        try:
            classification_service = ClassificationService(db)
            classification = await classification_service.classify_email(str(email.id))
            email_result["classification"] = classification

            category = classification.get("category", "").lower()
            subject = (email.subject or "").lower()
            body_preview = (email.body or "").lower()[:500]
            has_meeting_signal = (
                category == "meeting"
                or any(kw in subject for kw in MEETING_KEYWORDS)
                or any(kw in body_preview for kw in MEETING_KEYWORDS)
            )

            if has_meeting_signal:
                calendar_service = CalendarService(db)
                cal_result = await calendar_service.process_email_for_calendar(
                    email_id=str(email.id),
                    user_id=str(current_user.id),
                    dry_run=True,  # Don't auto-create — let user confirm via notification
                )
                email_result["calendar"] = {
                    "has_meeting": cal_result.get("has_meeting"),
                    "action": cal_result.get("action"),
                    "message": cal_result.get("message"),
                }

                calendar_context = cal_result.get("calendar_context")

                # Create interactive notification for meeting confirmation
                if cal_result.get("has_meeting") and cal_result.get("action") not in ("already_scheduled",):
                    proposed = calendar_context.get("proposed_meeting", {}) if calendar_context else {}
                    notification = Notification(
                        user_id=current_user.id,
                        type="confirm_meeting",
                        source="echo",
                        title=f"Meeting detected: {proposed.get('title', 'Meeting')}",
                        message=f"{proposed.get('date', '')} at {proposed.get('time', '')} — {cal_result.get('message', '')}",
                        action_type="confirm_meeting",
                        action_status="pending",
                        action_payload={
                            "email_id": str(email.id),
                            "summary": proposed.get("title", "Meeting"),
                            "start_time": proposed.get("start_time_iso"),
                            "end_time": proposed.get("end_time_iso"),
                            "attendees": proposed.get("attendees", []),
                            "location": proposed.get("location"),
                            "description": proposed.get("notes"),
                            "extraction": cal_result.get("extraction", {}),
                            "has_conflict": calendar_context.get("has_conflict", False) if calendar_context else False,
                        },
                    )
                    db.add(notification)
                    await db.commit()
                    email_result["notification_created"] = True

                # Still generate calendar-aware reply suggestion
                if cal_result.get("has_meeting") and calendar_context:
                    suggestion_service = SuggestionService(db)
                    suggestion = await suggestion_service.create_calendar_suggestion(
                        email_id=str(email.id),
                        user_id=str(current_user.id),
                        calendar_context=calendar_context,
                    )
                    email_result["suggestion"] = suggestion.suggestion_text
                    email_result["has_conflict"] = calendar_context.get("has_conflict")

            elif classification.get("needs_response"):
                suggestion_service = SuggestionService(db)
                suggestion = await suggestion_service.create_suggestion(
                    str(email.id), str(current_user.id)
                )
                email_result["suggestion"] = suggestion.suggestion_text

        except Exception as e:
            logger.error("inline_pipeline_error", email_id=str(email.id), error=str(e))
            email_result["pipeline_error"] = str(e)

        # --- Task extraction (runs for ALL emails, independent of meeting/suggestion) ---
        try:
            task_service = TaskService(db)
            extracted_tasks = await task_service.extract_tasks_from_email(
                email_id=str(email.id),
                user_id=str(current_user.id),
            )
            if extracted_tasks:
                email_result["tasks_extracted"] = len(extracted_tasks)
                email_result["task_titles"] = [t.title for t in extracted_tasks]
        except Exception as e:
            logger.warning("task_extraction_failed", email_id=str(email.id), error=str(e))

        processed.append(email_result)

    logger.info("manual_email_fetch", user_id=str(current_user.id), new_count=new_count, total_fetched=len(email_data_list))
    return {"fetched": len(email_data_list), "new": new_count, "processed": processed}


@router.get("/", response_model=List[EmailResponse])
async def list_emails(
    skip: int = 0,
    limit: int = 50,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    result = await db.execute(
        select(Email)
        .where(Email.user_id == current_user.id)
        .order_by(desc(Email.received_at))
        .offset(skip)
        .limit(limit)
    )
    emails = result.scalars().all()

    return emails


@router.get("/{email_id}", response_model=EmailResponse)
async def get_email(
    email_id: UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    result = await db.execute(
        select(Email)
        .where(Email.id == email_id)
        .where(Email.user_id == current_user.id)
    )
    email = result.scalar_one_or_none()

    if not email:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Email not found")

    return email


@router.get("/thread/{thread_id}", response_model=List[EmailResponse])
async def get_thread_emails(
    thread_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    result = await db.execute(
        select(Email)
        .where(Email.thread_id == thread_id)
        .where(Email.user_id == current_user.id)
        .order_by(Email.received_at)
    )
    emails = result.scalars().all()

    return emails
