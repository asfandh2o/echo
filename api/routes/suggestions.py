from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from sqlalchemy.orm import selectinload
from typing import List
from db.session import get_db
from models.user import User
from models.suggestion import Suggestion
from schemas.suggestion import SuggestionResponse, SuggestionFeedback
from api.deps import get_current_user
from services.suggestion_service import SuggestionService
from services.calendar_service import CalendarService
from services.gmail_service import GmailService
from tools.gmail_tool import GmailTool
from core.logging import get_logger
from uuid import UUID

router = APIRouter(prefix="/suggestions", tags=["suggestions"])
logger = get_logger(__name__)


@router.get("/", response_model=List[SuggestionResponse])
async def list_suggestions(
    status_filter: str = "pending",
    limit: int = 20,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    suggestion_service = SuggestionService(db)
    suggestions = await suggestion_service.get_pending_suggestions(
        user_id=str(current_user.id),
        limit=limit
    )

    return suggestions


@router.get("/{suggestion_id}", response_model=SuggestionResponse)
async def get_suggestion(
    suggestion_id: UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    result = await db.execute(
        select(Suggestion)
        .where(Suggestion.id == suggestion_id)
        .where(Suggestion.user_id == current_user.id)
    )
    suggestion = result.scalar_one_or_none()

    if not suggestion:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Suggestion not found")

    return suggestion


@router.post("/{suggestion_id}/feedback")
async def submit_suggestion_feedback(
    suggestion_id: UUID,
    feedback: SuggestionFeedback,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    suggestion_service = SuggestionService(db)

    feedback_log = await suggestion_service.submit_feedback(
        suggestion_id=str(suggestion_id),
        user_id=str(current_user.id),
        feedback_type=feedback.feedback_type,
        final_text=feedback.final_text
    )

    send_result = None

    # Send the reply for both accepted (AI draft) and rejected (user's own text)
    if feedback.feedback_type in ("accepted", "rejected") and (feedback.final_text or feedback.feedback_type == "accepted"):
        try:
            # Reload suggestion with email relationship
            result = await db.execute(
                select(Suggestion)
                .options(selectinload(Suggestion.email))
                .where(Suggestion.id == suggestion_id)
            )
            suggestion = result.scalar_one_or_none()

            if suggestion and suggestion.email:
                gmail_service = GmailService(current_user.encrypted_oauth_tokens)
                gmail_tool = GmailTool(gmail_service, str(current_user.id))

                # Extract email address from sender field (e.g. "Name <email>" -> "email")
                sender = suggestion.email.sender or ""
                reply_to = sender
                if "<" in sender and ">" in sender:
                    reply_to = sender.split("<")[1].split(">")[0]

                send_result = await gmail_tool.send_email_safe(
                    to=[reply_to],
                    subject=f"Re: {suggestion.email.subject}",
                    body=suggestion.final_text or suggestion.suggestion_text,
                    thread_id=suggestion.email.thread_id,
                    require_confirmation=False,
                    auto_approved=True
                )
                logger.info("suggestion_reply_sent", suggestion_id=str(suggestion_id), result=send_result)

                # If this is a calendar-aware suggestion, NOW create the calendar event
                # (only after user approved the reply)
                context_used = suggestion.context_used or {}
                if context_used.get("type") == "calendar_aware":
                    try:
                        proposed = context_used.get("proposed_meeting", {})
                        if proposed.get("start_time_iso") and proposed.get("title"):
                            calendar_service = CalendarService(db)
                            await calendar_service.process_email_for_calendar(
                                email_id=str(suggestion.email_id),
                                user_id=str(current_user.id),
                                dry_run=False,  # Actually create the event now
                            )
                            logger.info("calendar_event_created_on_approval", suggestion_id=str(suggestion_id))
                    except Exception as cal_err:
                        logger.error("calendar_event_creation_failed", suggestion_id=str(suggestion_id), error=str(cal_err))

            else:
                logger.warning("suggestion_send_skipped", suggestion_id=str(suggestion_id), reason="not found or no email")

        except Exception as e:
            logger.error("suggestion_send_failed", suggestion_id=str(suggestion_id), error=str(e))
            send_result = {"status": "error", "error": str(e)}

    logger.info(
        "suggestion_feedback_submitted",
        suggestion_id=str(suggestion_id),
        feedback_type=feedback.feedback_type
    )

    response = {"status": "success", "feedback_log_id": str(feedback_log.id)}
    if send_result:
        response["send_status"] = send_result.get("status", "unknown")
    return response
