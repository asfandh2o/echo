from typing import Dict, Any, Optional, List
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, desc
from models.calendar_event import CalendarEvent
from models.email import Email
from models.user import User
from services.llm_router import llm_router
from tools.calendar_tool import CalendarTool
from core.logging import get_logger
from datetime import datetime, timedelta
import re

logger = get_logger(__name__)


class CalendarService:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def process_email_for_calendar(self, email_id: str, user_id: str, dry_run: bool = False) -> Dict[str, Any]:
        # Check if this email has already been processed for calendar
        existing_result = await self.db.execute(
            select(CalendarEvent).where(
                CalendarEvent.email_id == email_id,
                CalendarEvent.user_id == user_id,
            )
        )
        existing_calendar_event = existing_result.scalar_one_or_none()
        if existing_calendar_event:
            logger.info("email_already_processed_for_calendar", email_id=email_id)
            return {
                "has_meeting": True,
                "action": "already_scheduled",
                "calendar_event": existing_calendar_event,
                "message": f"This email was already processed — event '{existing_calendar_event.summary}' exists",
                "calendar_context": {
                    "has_conflict": False,
                    "already_scheduled": True,
                    "proposed_meeting": {
                        "title": existing_calendar_event.summary,
                    },
                },
            }

        result = await self.db.execute(
            select(Email).where(Email.id == email_id)
        )
        email = result.scalar_one_or_none()

        if not email:
            raise ValueError(f"Email {email_id} not found")

        extraction = await llm_router.extract_meeting_details(
            email_content=email.body,
            subject=email.subject,
            sender=email.sender
        )

        if not extraction.get("has_meeting"):
            logger.info("no_meeting_detected", email_id=email_id)
            return {"has_meeting": False, "action": None, "message": "No meeting detected in email"}

        user_result = await self.db.execute(
            select(User).where(User.id == user_id)
        )
        user = user_result.scalar_one_or_none()

        if not user:
            raise ValueError(f"User {user_id} not found")

        calendar_tool = CalendarTool(user.encrypted_oauth_tokens, user_id)
        user_timezone = getattr(user, 'timezone', 'Asia/Karachi')
        user_email = user.email

        action = extraction.get("action", "create")

        if action == "create":
            return await self._create_meeting(calendar_tool, extraction, email_id, user_id, user_timezone, dry_run, user_email)
        elif action == "reschedule":
            return await self._reschedule_meeting(calendar_tool, extraction, email_id, user_id, user_timezone, dry_run, user_email)
        elif action == "cancel":
            logger.info("cancel_action_detected", email_id=email_id)
            return {"has_meeting": True, "action": "cancel", "message": "Cancel detected - requires manual action"}
        else:
            return {"has_meeting": True, "action": action, "message": f"Unknown action: {action}"}

    async def _create_meeting(
        self,
        calendar_tool: CalendarTool,
        extraction: Dict[str, Any],
        email_id: str,
        user_id: str,
        user_timezone: str = "Asia/Karachi",
        dry_run: bool = False,
        user_email: str = ""
    ) -> Dict[str, Any]:
        start_time, end_time = self._parse_meeting_times(extraction, user_timezone)

        summary = extraction.get("title") or "Meeting"
        attendees = self._filter_valid_emails(extraction.get("attendees", []))
        # Remove the user's own email from attendees — they are the organizer, not a guest
        if user_email:
            attendees = [a for a in attendees if a.lower() != user_email.lower()]
        location = extraction.get("location")
        notes = extraction.get("notes")
        duration = extraction.get("duration_minutes", 60) or 60

        # Always check for existing events at this time (events.list finds ALL events
        # including declined ones, unlike freebusy which only shows accepted/tentative)
        existing_events = await calendar_tool.get_conflicting_events(
            start_time.isoformat(),
            end_time.isoformat()
        )

        # Check if any existing event is the same meeting being proposed
        if existing_events:
            is_same_meeting = self._is_same_meeting(
                proposed_title=summary,
                proposed_attendees=attendees,
                conflicting_events=existing_events,
            )

            if is_same_meeting:
                logger.info(
                    "meeting_already_on_calendar",
                    email_id=email_id,
                    proposed_time=start_time.isoformat(),
                    summary=summary,
                )

                return {
                    "has_meeting": True,
                    "action": "already_scheduled",
                    "calendar_event": None,
                    "message": f"Meeting '{summary}' is already on the calendar",
                    "calendar_context": {
                        "has_conflict": False,
                        "already_scheduled": True,
                        "proposed_meeting": {
                            "title": summary,
                            "date": extraction.get("date"),
                            "time": extraction.get("time"),
                            "duration_minutes": duration,
                            "attendees": attendees,
                            "location": location,
                        },
                    },
                }

        # Now check availability (freebusy API — only counts accepted/tentative as busy)
        is_available = await calendar_tool.check_availability(
            start_time.isoformat(),
            end_time.isoformat()
        )

        if not is_available:
            # Genuine conflict with a different event
            free_slots = await calendar_tool.get_free_slots(
                around_time=start_time.isoformat(),
                duration_minutes=duration,
            )

            logger.info(
                "meeting_conflict_detected",
                email_id=email_id,
                proposed_time=start_time.isoformat(),
                conflicts=len(existing_events),
                free_alternatives=len(free_slots),
            )

            return {
                "has_meeting": True,
                "action": "conflict",
                "calendar_event": None,
                "message": f"Conflict detected for '{summary}' at {start_time.isoformat()}",
                "calendar_context": {
                    "has_conflict": True,
                    "conflicting_events": existing_events,
                    "free_slots": free_slots,
                    "proposed_meeting": {
                        "title": summary,
                        "date": extraction.get("date"),
                        "time": extraction.get("time"),
                        "duration_minutes": duration,
                        "attendees": attendees,
                        "location": location,
                    },
                },
            }

        # dry_run = just analyze, don't create the event (used by background tasks)
        if dry_run:
            logger.info(
                "meeting_ready_for_approval",
                email_id=email_id,
                summary=summary,
                proposed_time=start_time.isoformat(),
            )
            return {
                "has_meeting": True,
                "action": "pending_approval",
                "calendar_event": None,
                "message": f"Meeting '{summary}' ready for approval",
                "calendar_context": {
                    "has_conflict": False,
                    "proposed_meeting": {
                        "title": summary,
                        "date": extraction.get("date"),
                        "time": extraction.get("time"),
                        "duration_minutes": duration,
                        "attendees": attendees,
                        "location": location,
                        "notes": notes,
                        "start_time_iso": start_time.isoformat(),
                        "end_time_iso": end_time.isoformat(),
                    },
                },
                "extraction": extraction,
            }

        # No conflict and no duplicate — create the event
        google_event = await calendar_tool.create_event(
            summary=summary,
            start_time=start_time.isoformat(),
            end_time=end_time.isoformat(),
            attendees=attendees,
            description=notes,
            location=location
        )

        calendar_event = CalendarEvent(
            user_id=user_id,
            email_id=email_id,
            google_event_id=google_event["id"],
            summary=summary,
            start_time=start_time,
            end_time=end_time,
            attendees=attendees,
            location=location,
            status="created",
            action_type="create",
            llm_extraction=extraction,
            extra_data={"available": True, "html_link": google_event.get("html_link")}
        )

        self.db.add(calendar_event)
        await self.db.commit()
        await self.db.refresh(calendar_event)

        logger.info(
            "meeting_created_from_email",
            email_id=email_id,
            google_event_id=google_event["id"],
            summary=summary
        )

        return {
            "has_meeting": True,
            "action": "create",
            "calendar_event": calendar_event,
            "message": f"Meeting '{summary}' created",
            "calendar_context": {
                "has_conflict": False,
                "proposed_meeting": {
                    "title": summary,
                    "date": extraction.get("date"),
                    "time": extraction.get("time"),
                    "duration_minutes": duration,
                    "attendees": attendees,
                    "location": location,
                },
            },
        }

    async def _reschedule_meeting(
        self,
        calendar_tool: CalendarTool,
        extraction: Dict[str, Any],
        email_id: str,
        user_id: str,
        user_timezone: str = "Asia/Karachi",
        dry_run: bool = False,
        user_email: str = ""
    ) -> Dict[str, Any]:
        ref = extraction.get("original_event_reference") or extraction.get("title")

        existing_event = None
        if ref:
            existing_event = await calendar_tool.find_event_by_query(ref)

        if not existing_event:
            db_result = await self.db.execute(
                select(CalendarEvent)
                .where(CalendarEvent.user_id == user_id)
                .order_by(desc(CalendarEvent.created_at))
                .limit(10)
            )
            recent_events = db_result.scalars().all()
            for evt in recent_events:
                if ref and ref.lower() in evt.summary.lower():
                    existing_event = await calendar_tool.find_event_by_query(evt.summary)
                    break

        if not existing_event:
            logger.warning("reschedule_event_not_found", email_id=email_id, reference=ref)
            return await self._create_meeting(calendar_tool, extraction, email_id, user_id, user_timezone, dry_run, user_email)

        new_start, new_end = self._parse_meeting_times(extraction, user_timezone)
        duration = extraction.get("duration_minutes", 60) or 60
        summary = existing_event.get("summary", extraction.get("title", "Meeting"))
        attendees = self._filter_valid_emails(extraction.get("attendees", []))
        if user_email:
            attendees = [a for a in attendees if a.lower() != user_email.lower()]

        # Check if the new proposed time has a conflict
        is_available = await calendar_tool.check_availability(
            new_start.isoformat(),
            new_end.isoformat()
        )

        if not is_available:
            conflicting_events = await calendar_tool.get_conflicting_events(
                new_start.isoformat(),
                new_end.isoformat()
            )
            free_slots = await calendar_tool.get_free_slots(
                around_time=new_start.isoformat(),
                duration_minutes=duration,
            )

            logger.info(
                "reschedule_conflict_detected",
                email_id=email_id,
                proposed_time=new_start.isoformat(),
                conflicts=len(conflicting_events),
            )

            return {
                "has_meeting": True,
                "action": "conflict",
                "calendar_event": None,
                "message": f"Conflict detected for rescheduling '{summary}' to {new_start.isoformat()}",
                "calendar_context": {
                    "has_conflict": True,
                    "conflicting_events": conflicting_events,
                    "free_slots": free_slots,
                    "proposed_meeting": {
                        "title": summary,
                        "date": extraction.get("date"),
                        "time": extraction.get("time"),
                        "duration_minutes": duration,
                        "attendees": attendees,
                    },
                },
            }

        # dry_run = just analyze, don't modify the event (used by background tasks)
        if dry_run:
            return {
                "has_meeting": True,
                "action": "pending_approval",
                "calendar_event": None,
                "message": f"Reschedule of '{summary}' ready for approval",
                "calendar_context": {
                    "has_conflict": False,
                    "proposed_meeting": {
                        "title": summary,
                        "date": extraction.get("date"),
                        "time": extraction.get("time"),
                        "duration_minutes": duration,
                        "attendees": attendees,
                        "start_time_iso": new_start.isoformat(),
                        "end_time_iso": new_end.isoformat(),
                    },
                },
                "extraction": extraction,
            }

        google_event = await calendar_tool.update_event(
            event_id=existing_event["id"],
            start_time=new_start.isoformat(),
            end_time=new_end.isoformat()
        )

        calendar_event = CalendarEvent(
            user_id=user_id,
            email_id=email_id,
            google_event_id=google_event["id"],
            summary=google_event.get("summary", summary),
            start_time=new_start,
            end_time=new_end,
            attendees=google_event.get("attendees", []),
            status="rescheduled",
            action_type="reschedule",
            llm_extraction=extraction,
            extra_data={"previous_event": existing_event, "html_link": google_event.get("html_link")}
        )

        self.db.add(calendar_event)
        await self.db.commit()
        await self.db.refresh(calendar_event)

        logger.info(
            "meeting_rescheduled_from_email",
            email_id=email_id,
            google_event_id=google_event["id"]
        )

        return {
            "has_meeting": True,
            "action": "reschedule",
            "calendar_event": calendar_event,
            "message": f"Meeting rescheduled to {new_start.isoformat()}",
            "calendar_context": {
                "has_conflict": False,
                "proposed_meeting": {
                    "title": summary,
                    "date": extraction.get("date"),
                    "time": extraction.get("time"),
                    "duration_minutes": duration,
                },
            },
        }

    async def reschedule_event(
        self,
        calendar_event_id: str,
        new_start: datetime,
        new_end: datetime,
        user_id: str
    ) -> CalendarEvent:
        result = await self.db.execute(
            select(CalendarEvent)
            .where(CalendarEvent.id == calendar_event_id)
            .where(CalendarEvent.user_id == user_id)
        )
        calendar_event = result.scalar_one_or_none()

        if not calendar_event:
            raise ValueError(f"Calendar event {calendar_event_id} not found")

        user_result = await self.db.execute(
            select(User).where(User.id == user_id)
        )
        user = user_result.scalar_one_or_none()

        calendar_tool = CalendarTool(user.encrypted_oauth_tokens, user_id)

        await calendar_tool.update_event(
            event_id=calendar_event.google_event_id,
            start_time=new_start.isoformat(),
            end_time=new_end.isoformat()
        )

        calendar_event.start_time = new_start
        calendar_event.end_time = new_end
        calendar_event.status = "rescheduled"

        await self.db.commit()
        await self.db.refresh(calendar_event)

        logger.info(
            "meeting_rescheduled_manually",
            calendar_event_id=calendar_event_id,
            new_start=new_start.isoformat()
        )

        return calendar_event

    @staticmethod
    def _is_same_meeting(
        proposed_title: str,
        proposed_attendees: List[str],
        conflicting_events: List[Dict[str, Any]],
    ) -> bool:
        """Check if a conflicting calendar event is actually the same meeting being proposed.

        Requires BOTH title similarity AND attendee overlap to avoid false positives
        (e.g. recurring meetings with same people but different purpose).
        """
        proposed_title_lower = (proposed_title or "").lower().strip()
        proposed_attendee_set = {e.lower() for e in (proposed_attendees or [])}

        for event in conflicting_events:
            event_summary = (event.get("summary") or "").lower().strip()

            # Check title similarity (substring match in either direction)
            title_match = (
                proposed_title_lower in event_summary
                or event_summary in proposed_title_lower
            ) if proposed_title_lower and event_summary else False

            # Check attendee overlap
            event_attendees = set()
            for att in event.get("attendees", []):
                if isinstance(att, dict):
                    event_attendees.add(att.get("email", "").lower())
                elif isinstance(att, str):
                    event_attendees.add(att.lower())

            attendee_overlap = bool(proposed_attendee_set & event_attendees)

            # Require BOTH title AND attendee match to confirm same meeting
            if title_match and attendee_overlap:
                return True

            # Also match if the event organizer sent the email (organizer == proposed attendee)
            organizer = event.get("organizer", {})
            organizer_email = ""
            if isinstance(organizer, dict):
                organizer_email = organizer.get("email", "").lower()
            elif isinstance(organizer, str):
                organizer_email = organizer.lower()

            if organizer_email and organizer_email in proposed_attendee_set and title_match:
                return True

        return False

    @staticmethod
    def _filter_valid_emails(emails: List) -> List[str]:
        if not emails:
            return []
        email_re = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
        return [e for e in emails if isinstance(e, str) and email_re.match(e)]

    def _parse_meeting_times(self, extraction: Dict[str, Any], user_timezone: str = "Asia/Karachi") -> tuple:
        from zoneinfo import ZoneInfo

        date_str = extraction.get("date")
        time_str = extraction.get("time")
        duration = extraction.get("duration_minutes", 60) or 60
        user_tz = ZoneInfo(user_timezone)

        # Parse the hour/minute from extracted time (e.g. "15:00")
        hour, minute = 9, 0
        if time_str:
            try:
                parts = time_str.split(":")
                hour = int(parts[0])
                minute = int(parts[1]) if len(parts) > 1 else 0
            except (ValueError, IndexError):
                hour, minute = 9, 0

        if date_str:
            try:
                start_time = datetime.fromisoformat(f"{date_str}T{hour:02d}:{minute:02d}:00")
            except ValueError:
                start_time = datetime.utcnow() + timedelta(days=1)
                start_time = start_time.replace(hour=hour, minute=minute, second=0, microsecond=0)
        else:
            # No date extracted — default to tomorrow
            start_time = datetime.utcnow() + timedelta(days=1)
            start_time = start_time.replace(hour=hour, minute=minute, second=0, microsecond=0)

        # Treat the parsed time as user's local time and convert to UTC
        start_time = start_time.replace(tzinfo=user_tz)

        end_time = start_time + timedelta(minutes=duration)

        return start_time, end_time

    async def get_managed_events(self, user_id: str, limit: int = 20):
        result = await self.db.execute(
            select(CalendarEvent)
            .where(CalendarEvent.user_id == user_id)
            .order_by(desc(CalendarEvent.created_at))
            .limit(limit)
        )
        return result.scalars().all()
