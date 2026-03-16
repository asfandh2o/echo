from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from typing import List
from uuid import UUID
from db.session import get_db
from models.user import User
from schemas.calendar_event import (
    CalendarCreateRequest,
    CalendarRescheduleRequest,
    CalendarEventResponse,
    CalendarProcessResponse,
)
from api.deps import get_current_user
from services.calendar_service import CalendarService
from services.suggestion_service import SuggestionService
from tools.calendar_tool import CalendarTool
from core.logging import get_logger

router = APIRouter(prefix="/calendar", tags=["calendar"])
logger = get_logger(__name__)


@router.get("/events")
async def list_upcoming_events(
    days_ahead: int = 7,
    max_results: int = 10,
    current_user: User = Depends(get_current_user),
):
    calendar_tool = CalendarTool(current_user.encrypted_oauth_tokens, str(current_user.id))
    events = await calendar_tool.get_upcoming_events(days_ahead=days_ahead, max_results=max_results)
    return events


@router.get("/events/managed", response_model=List[CalendarEventResponse])
async def list_managed_events(
    limit: int = 20,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    calendar_service = CalendarService(db)
    events = await calendar_service.get_managed_events(str(current_user.id), limit=limit)
    return events


@router.post("/events", response_model=CalendarEventResponse)
async def create_event(
    request: CalendarCreateRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    calendar_tool = CalendarTool(current_user.encrypted_oauth_tokens, str(current_user.id))

    google_event = await calendar_tool.create_event(
        summary=request.summary,
        start_time=request.start_time.isoformat(),
        end_time=request.end_time.isoformat(),
        attendees=request.attendees,
        description=request.description,
        location=request.location,
    )

    from models.calendar_event import CalendarEvent

    calendar_event = CalendarEvent(
        user_id=current_user.id,
        google_event_id=google_event["id"],
        summary=request.summary,
        start_time=request.start_time,
        end_time=request.end_time,
        attendees=request.attendees,
        location=request.location,
        status="created",
        action_type="create",
        llm_extraction={},
        extra_data={"html_link": google_event.get("html_link"), "source": "manual"},
    )

    db.add(calendar_event)
    await db.commit()
    await db.refresh(calendar_event)

    logger.info("calendar_event_created_via_api", event_id=str(calendar_event.id))

    return calendar_event


@router.put("/events/{event_id}/reschedule", response_model=CalendarEventResponse)
async def reschedule_event(
    event_id: UUID,
    request: CalendarRescheduleRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    calendar_service = CalendarService(db)

    try:
        updated = await calendar_service.reschedule_event(
            calendar_event_id=str(event_id),
            new_start=request.new_start_time,
            new_end=request.new_end_time,
            user_id=str(current_user.id),
        )
        return updated
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))


@router.post("/process-email/{email_id}", response_model=CalendarProcessResponse)
async def process_email_for_calendar(
    email_id: UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    calendar_service = CalendarService(db)

    try:
        result = await calendar_service.process_email_for_calendar(
            email_id=str(email_id),
            user_id=str(current_user.id),
        )

        calendar_event = result.get("calendar_event")
        calendar_context = result.get("calendar_context")

        # Generate calendar-aware reply suggestion inline
        suggested_reply = None
        if result.get("has_meeting") and calendar_context:
            suggestion_service = SuggestionService(db)
            suggestion = await suggestion_service.create_calendar_suggestion(
                email_id=str(email_id),
                user_id=str(current_user.id),
                calendar_context=calendar_context,
            )
            suggested_reply = suggestion.suggestion_text

        return CalendarProcessResponse(
            has_meeting=result["has_meeting"],
            action=result.get("action"),
            calendar_event=CalendarEventResponse.model_validate(calendar_event) if calendar_event else None,
            message=result["message"],
            suggested_reply=suggested_reply,
            has_conflict=calendar_context.get("has_conflict") if calendar_context else None,
            free_slots=calendar_context.get("free_slots") if calendar_context else None,
        )
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    except Exception as e:
        logger.error("process_email_for_calendar_failed", email_id=str(email_id), error=str(e))
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))
