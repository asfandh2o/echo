from typing import Optional, List
from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, desc, func
from pydantic import BaseModel
from db.session import get_db
from models.user import User
from models.email import Email
from models.suggestion import Suggestion
from models.contact_profile import ContactProfile
from api.deps import get_current_user
from services.llm_router import llm_router
from services.gmail_service import GmailService
from tools.gmail_tool import GmailTool
from tools.calendar_tool import CalendarTool
from core.logging import get_logger
from core.config import settings
from datetime import datetime, timedelta
import re
import httpx

router = APIRouter(prefix="/chat", tags=["chat"])
logger = get_logger(__name__)


class ChatRequest(BaseModel):
    message: str


class ContactOption(BaseModel):
    name: str
    email: str


class EmailDraft(BaseModel):
    to: str
    subject: str
    body: str


class CalendarEventResult(BaseModel):
    status: str  # "created", "conflict", "already_scheduled", "error"
    summary: Optional[str] = None
    start_time: Optional[str] = None
    end_time: Optional[str] = None
    attendees: Optional[List[str]] = None
    message: Optional[str] = None


class ChatResponse(BaseModel):
    reply: str
    email_draft: Optional[EmailDraft] = None
    contact_options: Optional[List[ContactOption]] = None
    calendar_event: Optional[CalendarEventResult] = None


class SendDraftRequest(BaseModel):
    to: str
    subject: str
    body: str


MEETING_KEYWORDS = ["meeting", "meet", "schedule", "calendar", "reschedule", "appointment", "call", "sync", "standup"]
ASKING_SIGNALS = ["work for you", "does that work", "let me know", "available", "suit you",
                  "convenient", "would you", "can you", "are you free", "what do you think",
                  "sound good", "okay with you", "confirm", "check with"]


class SendDraftResponse(BaseModel):
    status: str
    message_id: Optional[str] = None
    calendar_event_created: Optional[str] = None
    error: Optional[str] = None


@router.post("/send", response_model=ChatResponse)
async def send_chat_message(
    body: ChatRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    message = body.message.strip()
    if not message:
        return ChatResponse(reply="Please type a message.")

    # Gather context about the user's inbox, calendar, and documents
    context = await _build_user_context(db, current_user, user_message=message)

    result = await llm_router.chat_with_context(
        user_message=message,
        inbox_context=context,
    )

    logger.info("chat_message", user_id=str(current_user.id), message_length=len(message))

    if result["type"] == "calendar_event":
        # Direct calendar event creation from chat
        cal_data = result["calendar"]
        cal_result = await _create_calendar_from_chat(
            db, current_user, cal_data
        )
        return ChatResponse(
            reply=cal_result.get("reply", "Calendar event processed."),
            calendar_event=CalendarEventResult(
                status=cal_result["status"],
                summary=cal_result.get("summary"),
                start_time=cal_result.get("start_time"),
                end_time=cal_result.get("end_time"),
                attendees=cal_result.get("attendees"),
                message=cal_result.get("message"),
            ),
        )

    if result["type"] == "email_draft":
        draft = result["email_draft"]
        to_value = draft.get("to", "")
        contact_options = None

        # Resolve name to email if the "to" field isn't a valid email address
        if to_value and not re.match(r'^[^@\s]+@[^@\s]+\.[^@\s]+$', to_value):
            matches = await _resolve_contact(db, str(current_user.id), to_value)
            if len(matches) == 1:
                to_value = matches[0]["email"]
            elif len(matches) > 1:
                contact_options = [ContactOption(name=m["name"], email=m["email"]) for m in matches]
            else:
                # No contact matches — try HERA project team lookup
                hera_result = await _resolve_hera_project_team(to_value, current_user.email)
                if hera_result:
                    # Auto-fill TO with all team member emails
                    to_value = ", ".join(m["email"] for m in hera_result)

        reply_text = "Here's your draft email:"
        # If we resolved to multiple team members, mention it
        if to_value and ", " in to_value:
            count = len(to_value.split(", "))
            reply_text = f"Here's your draft email to {count} team members:"

        return ChatResponse(
            reply=reply_text,
            email_draft=EmailDraft(
                to=to_value,
                subject=draft.get("subject", ""),
                body=draft.get("body", ""),
            ),
            contact_options=contact_options,
        )
    return ChatResponse(reply=result["reply"])


@router.post("/send-draft", response_model=SendDraftResponse)
async def send_draft_email(
    body: SendDraftRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    try:
        gmail_service = GmailService(current_user.encrypted_oauth_tokens)
        gmail_tool = GmailTool(gmail_service, str(current_user.id))

        # Support comma-separated TO for multiple recipients
        recipients = [addr.strip() for addr in body.to.split(",") if addr.strip()]

        result = await gmail_tool.send_email_safe(
            to=recipients,
            subject=body.subject,
            body=body.body,
            require_confirmation=False,
            auto_approved=True,
        )

        logger.info("chat_draft_sent", user_id=str(current_user.id), to=body.to)

        calendar_event_summary = None

        # Check if the sent email contains meeting language — if so, create a calendar event
        body_lower = body.body.lower()
        subject_lower = body.subject.lower()
        has_meeting_signal = any(kw in body_lower or kw in subject_lower for kw in MEETING_KEYWORDS)

        if has_meeting_signal:
            is_asking = any(sig in body_lower for sig in ASKING_SIGNALS)

            try:
                from services.calendar_service import CalendarService

                extraction = await llm_router.extract_meeting_details(
                    email_content=body.body,
                    subject=body.subject,
                    sender=f"{current_user.email} (sent by me to {body.to})",
                )

                if extraction.get("has_meeting") and extraction.get("action") == "create":
                    attendees = extraction.get("attendees", [])
                    for r in recipients:
                        if r not in attendees:
                            attendees.append(r)
                    extraction["attendees"] = attendees

                    if is_asking:
                        # Store pending proposal in Redis — wait for positive response
                        await _store_pending_meeting(
                            user_id=str(current_user.id),
                            recipients=recipients,
                            extraction=extraction,
                            subject=body.subject,
                        )
                        calendar_event_summary = "pending confirmation"
                        logger.info("chat_draft_meeting_proposal_stored",
                                    recipients=recipients,
                                    title=extraction.get("title"))
                    else:
                        # Directly create calendar event (telling, not asking)
                        calendar_service = CalendarService(db)
                        calendar_tool_instance = CalendarTool(current_user.encrypted_oauth_tokens, str(current_user.id))
                        user_timezone = getattr(current_user, 'timezone', 'Asia/Karachi')

                        cal_result = await calendar_service._create_meeting(
                            calendar_tool=calendar_tool_instance,
                            extraction=extraction,
                            email_id=str(current_user.id),
                            user_id=str(current_user.id),
                            user_timezone=user_timezone,
                            dry_run=False,
                            user_email=current_user.email,
                        )

                        if cal_result.get("action") == "create" and cal_result.get("calendar_event"):
                            calendar_event_summary = cal_result["calendar_event"].summary
                            logger.info("chat_draft_calendar_event_created", summary=calendar_event_summary)
                        elif cal_result.get("action") == "already_scheduled":
                            calendar_event_summary = "already on calendar"

            except Exception as cal_err:
                logger.warning("chat_draft_calendar_failed", error=str(cal_err))

        return SendDraftResponse(
            status=result.get("status", "sent"),
            message_id=result.get("message_id"),
            calendar_event_created=calendar_event_summary,
        )
    except Exception as e:
        logger.error("chat_draft_send_failed", error=str(e))
        return SendDraftResponse(status="error", error=str(e))


async def _create_calendar_from_chat(
    db: AsyncSession,
    current_user: User,
    cal_data: dict,
) -> dict:
    """Create a calendar event directly from a chat command.

    Resolves project team members from HERA if a project is referenced,
    then creates the event via Google Calendar API.
    """
    from services.calendar_service import CalendarService

    title = cal_data.get("title", "Meeting")
    date_str = cal_data.get("date")
    time_str = cal_data.get("time")
    duration = cal_data.get("duration_minutes", 60) or 60
    project_name = cal_data.get("project", "")

    # Resolve attendees from HERA project team
    attendees = []
    if project_name:
        hera_team = await _resolve_hera_project_team(project_name, current_user.email)
        attendees = [m["email"] for m in hera_team]

    try:
        calendar_tool = CalendarTool(current_user.encrypted_oauth_tokens, str(current_user.id))
        user_timezone = getattr(current_user, 'timezone', 'Asia/Karachi')

        # Build extraction dict matching what CalendarService._create_meeting expects
        extraction = {
            "has_meeting": True,
            "action": "create",
            "title": title,
            "date": date_str,
            "time": time_str,
            "duration_minutes": duration,
            "attendees": attendees,
            "location": None,
            "notes": f"Created by ECHO from chat",
        }

        calendar_service = CalendarService(db)
        cal_result = await calendar_service._create_meeting(
            calendar_tool=calendar_tool,
            extraction=extraction,
            email_id=str(current_user.id),  # no email, use user_id as placeholder
            user_id=str(current_user.id),
            user_timezone=user_timezone,
            dry_run=False,
            user_email=current_user.email,
        )

        action = cal_result.get("action")
        if action == "create" and cal_result.get("calendar_event"):
            evt = cal_result["calendar_event"]
            logger.info("chat_calendar_created", summary=evt.summary, attendees=attendees)
            att_names = ", ".join(attendees) if attendees else "no attendees"
            return {
                "status": "created",
                "reply": f"Calendar event '{evt.summary}' created with {att_names} invited!",
                "summary": evt.summary,
                "start_time": evt.start_time.isoformat() if evt.start_time else None,
                "end_time": evt.end_time.isoformat() if evt.end_time else None,
                "attendees": attendees,
                "message": f"Event created successfully",
            }
        elif action == "already_scheduled":
            return {
                "status": "already_scheduled",
                "reply": cal_result.get("message", "This meeting is already on your calendar."),
                "summary": title,
                "message": "Already scheduled",
            }
        elif action == "conflict":
            free_slots = cal_result.get("calendar_context", {}).get("free_slots", [])
            alt_text = ""
            if free_slots:
                alt_text = " Available alternatives: " + ", ".join(s.get("start", "") for s in free_slots[:3])
            return {
                "status": "conflict",
                "reply": f"There's a conflict at that time.{alt_text}",
                "summary": title,
                "message": "Time conflict detected",
            }
        else:
            return {
                "status": "error",
                "reply": f"Couldn't create the event: {cal_result.get('message', 'unknown error')}",
                "message": cal_result.get("message"),
            }
    except Exception as e:
        logger.error("chat_calendar_create_failed", error=str(e))
        return {
            "status": "error",
            "reply": f"Failed to create calendar event: {str(e)}",
            "message": str(e),
        }


async def _store_pending_meeting(
    user_id: str,
    recipients: list,
    extraction: dict,
    subject: str,
) -> None:
    """Store a pending meeting proposal in Redis.

    When the user sends an email ASKING if a time works, we store the
    meeting details so that when the recipient responds positively,
    we can auto-create the calendar event.
    """
    import json as _json
    import redis.asyncio as aioredis

    try:
        r = aioredis.from_url(settings.REDIS_URL, decode_responses=True)
        proposal = {
            "user_id": user_id,
            "recipients": recipients,
            "subject": subject,
            "title": extraction.get("title", subject),
            "date": extraction.get("date"),
            "time": extraction.get("time"),
            "duration_minutes": extraction.get("duration_minutes", 60),
            "attendees": extraction.get("attendees", []),
            "location": extraction.get("location"),
            "stored_at": datetime.utcnow().isoformat(),
        }
        # Store one key per recipient so we can look up by sender email
        for recipient in recipients:
            key = f"pending_meeting:{user_id}:{recipient.lower()}"
            await r.setex(key, 7 * 86400, _json.dumps(proposal))  # TTL: 7 days
        await r.aclose()
        logger.info("pending_meeting_stored", user_id=user_id, recipients=recipients)
    except Exception as e:
        logger.warning("pending_meeting_store_failed", error=str(e))


async def _resolve_contact(db: AsyncSession, user_id: str, name: str) -> list:
    """Resolve a name to email addresses from the user's contact history.

    Searches both display_name and email_address (local part) for matches.
    """
    from sqlalchemy import or_

    search = name.strip().lower()
    result = await db.execute(
        select(ContactProfile.display_name, ContactProfile.email_address)
        .where(ContactProfile.user_id == user_id)
        .where(or_(
            ContactProfile.display_name.ilike(f"%{search}%"),
            ContactProfile.email_address.ilike(f"%{search}%"),
        ))
        .order_by(desc(ContactProfile.email_count))
        .limit(5)
    )
    return [{"name": row[0] or row[1], "email": row[1]} for row in result.all()]


async def _resolve_hera_project_team(to_text: str, current_user_email: str) -> list:
    """Query HERA to find project team members when TO refers to a project/team.

    Extracts likely project keywords from the TO text, calls HERA's
    team-lookup endpoint, and returns team members (excluding the current user).
    """
    if not settings.HERA_API_URL or not settings.HERA_API_KEY:
        return []

    # Extract meaningful search terms (strip filler words)
    filler = {"the", "people", "i", "am", "working", "with", "on", "my", "team",
              "members", "of", "in", "project", "all", "everyone", "send", "email",
              "to", "a", "an", "for", "from", "about", "system", "app"}
    words = to_text.lower().split()
    search_terms = [w for w in words if w not in filler and len(w) > 1]
    search = " ".join(search_terms).strip()

    if not search:
        # Fallback: use the full text
        search = to_text.strip()

    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.post(
                f"{settings.HERA_API_URL}/prompts/team-lookup",
                json={"api_key": settings.HERA_API_KEY, "search": search},
            )
            if resp.status_code != 200:
                logger.warning("hera_team_lookup_failed", status=resp.status_code)
                return []

            data = resp.json()
            projects = data.get("projects", [])
            if not projects:
                return []

            # Use the first matching project's team members
            members = projects[0].get("team_members", [])
            # Exclude the current user from the TO list
            members = [m for m in members if m["email"].lower() != current_user_email.lower()]
            logger.info("hera_team_resolved",
                        project=projects[0].get("project_name"),
                        members=len(members))
            return members
    except Exception as e:
        logger.warning("hera_team_lookup_error", error=str(e))
        return []


async def _build_user_context(db: AsyncSession, user: User, user_message: str = "") -> str:
    """Build a concise summary of the user's inbox and calendar for chat context."""
    user_id = str(user.id)
    since = datetime.utcnow() - timedelta(days=3)

    # Recent emails (last 3 days)
    email_result = await db.execute(
        select(Email)
        .where(Email.user_id == user_id, Email.received_at >= since)
        .order_by(desc(Email.received_at))
        .limit(15)
    )
    emails = email_result.scalars().all()

    # Pending suggestions
    suggestion_result = await db.execute(
        select(Suggestion)
        .where(Suggestion.user_id == user_id, Suggestion.status == "pending")
        .order_by(desc(Suggestion.created_at))
        .limit(10)
    )
    suggestions = suggestion_result.scalars().all()

    # Total counts
    total_result = await db.execute(
        select(func.count()).select_from(Email).where(Email.user_id == user_id)
    )
    total_emails = total_result.scalar() or 0

    lines = [f"User has {total_emails} total emails. {len(emails)} received in the last 3 days."]
    lines.append(f"{len(suggestions)} pending reply suggestions.\n")

    # Fetch real calendar events (next 7 days) — this is the source of truth
    try:
        calendar_tool = CalendarTool(user.encrypted_oauth_tokens, user_id)
        calendar_events = await calendar_tool.get_upcoming_events(days_ahead=7, max_results=10)
        if calendar_events:
            lines.append("Upcoming calendar events (next 7 days):")
            for evt in calendar_events:
                raw_start = evt.get("start", "")
                raw_end = evt.get("end", "")
                summary = evt.get("summary", "No title")
                attendees = evt.get("attendees", [])
                att_str = f" | Attendees: {', '.join(attendees[:3])}" if attendees else ""
                # Format to human-readable (use time as-is from calendar)
                start_str = _format_event_time(raw_start)
                end_str = _format_event_time(raw_end, time_only=True)
                lines.append(f"- \"{summary}\" on {start_str} to {end_str}{att_str}")
            lines.append("")
        else:
            lines.append("No upcoming calendar events in the next 7 days.\n")
    except Exception as e:
        logger.warning("chat_calendar_fetch_failed", error=str(e))
        lines.append("Calendar data unavailable.\n")

    # Fetch HERA project data so the LLM knows about active projects and team members
    try:
        if settings.HERA_API_URL and settings.HERA_API_KEY:
            async with httpx.AsyncClient(timeout=8.0) as client:
                resp = await client.post(
                    f"{settings.HERA_API_URL}/prompts/team-lookup",
                    json={"api_key": settings.HERA_API_KEY, "search": ""},
                )
                if resp.status_code == 200:
                    hera_projects = resp.json().get("projects", [])
                    if hera_projects:
                        lines.append("HERA projects (task management — team members):")
                        for p in hera_projects:
                            members = ", ".join(f'{m["name"]} ({m["email"]})' for m in p["team_members"])
                            lines.append(f'  - "{p["project_name"]}" — Team: {members}')
                        lines.append("")
    except Exception as e:
        logger.warning("chat_hera_projects_failed", error=str(e))

    # Always provide the LLM with a list of available documents + search for relevant content
    try:
        from services.document_service import DocumentService
        doc_service = DocumentService()

        # Always include a document inventory so the LLM knows what exists
        all_docs = await doc_service.list_user_documents(db, user_id)
        if all_docs:
            lines.append(f"Google Drive documents available ({len(all_docs)} indexed):")
            for d in all_docs:
                lines.append(f'  - "{d["name"]}" ({d["mime_type"]}, updated {d["modified_at"]})')
            lines.append("")

        # Search for relevant document content based on user's question
        seen_chunks = set()
        all_doc_results = []

        if user_message:
            msg_results = await doc_service.search_documents(db, user_id, user_message, limit=3)
            for doc in msg_results:
                chunk_key = (doc["document_name"], doc["content"][:100])
                if chunk_key not in seen_chunks:
                    seen_chunks.add(chunk_key)
                    all_doc_results.append(doc)

        # Secondary: search based on recent email topics (if room left)
        if emails and len(all_doc_results) < 3:
            topics = " ".join([e.subject for e in emails[:5] if e.subject])
            if topics.strip():
                topic_results = await doc_service.search_documents(db, user_id, topics, limit=3 - len(all_doc_results))
                for doc in topic_results:
                    chunk_key = (doc["document_name"], doc["content"][:100])
                    if chunk_key not in seen_chunks:
                        seen_chunks.add(chunk_key)
                        all_doc_results.append(doc)

        if all_doc_results:
            lines.append("Relevant document content (from Google Drive):")
            for doc in all_doc_results:
                lines.append(f'[Source: "{doc["document_name"]}" (updated {doc["modified_at"]})]')
                lines.append(doc["content"][:1500])
            lines.append("")
    except Exception as e:
        logger.warning("chat_document_search_failed", error=str(e))

    if emails:
        lines.append("Recent emails:")
        for e in emails[:10]:
            category = ""
            if e.classification and isinstance(e.classification, dict):
                category = e.classification.get("category", "")
            urgent = ""
            if e.classification and isinstance(e.classification, dict):
                if e.classification.get("is_urgent"):
                    urgent = " [URGENT]"
            lines.append(f"- From: {e.sender} | Subject: {e.subject} | Category: {category}{urgent}")

    if suggestions:
        lines.append("\nPending suggestions:")
        for s in suggestions:
            preview = (s.suggestion_text or "")[:80]
            lines.append(f"- For email {s.email_id}: {preview}...")

    return "\n".join(lines)


def _format_event_time(iso_str: str, time_only: bool = False) -> str:
    """Convert ISO datetime to human-readable format like 'Thursday Feb 19 at 3:30 PM'.

    Parses the time directly from the ISO string without timezone conversion,
    so times match exactly what Google Calendar shows. Uses manual formatting
    to avoid Windows strftime issues with %-I / %-d codes.
    """
    if not iso_str:
        return "unknown time"
    try:
        if "T" not in iso_str:
            dt = datetime.fromisoformat(iso_str)
            day_name = dt.strftime("%A")
            month_name = dt.strftime("%b")
            return f"{day_name} {month_name} {dt.day} (all day)"

        # Parse the ISO string — use the time components as-is (no tz conversion)
        dt = datetime.fromisoformat(iso_str.replace("Z", "+00:00"))

        hour_12 = dt.hour % 12 or 12
        am_pm = "AM" if dt.hour < 12 else "PM"
        minute = f"{dt.minute:02d}"

        if time_only:
            return f"{hour_12}:{minute} {am_pm}"

        day_name = dt.strftime("%A")
        month_name = dt.strftime("%b")
        return f"{day_name} {month_name} {dt.day} at {hour_12}:{minute} {am_pm}"
    except (ValueError, TypeError):
        return iso_str
