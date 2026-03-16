from workers.celery_app import celery_app
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy import select, update
from models.user import User
from models.email import Email
from services.gmail_service import GmailService
from services.classification_service import ClassificationService
from services.memory_service import MemoryService
from services.suggestion_service import SuggestionService
from services.style_service import StyleService
from services.digest_service import DigestService
from services.calendar_service import CalendarService
from core.config import settings
from core.logging import get_logger
import asyncio

logger = get_logger(__name__)


def _create_session_factory():
    """Create a fresh engine and session factory for each task's event loop."""
    engine = create_async_engine(
        settings.DATABASE_URL,
        pool_size=5,
        max_overflow=5,
        pool_pre_ping=True,
    )
    return async_sessionmaker(
        engine,
        class_=AsyncSession,
        expire_on_commit=False,
        autocommit=False,
        autoflush=False,
    )


@celery_app.task(name="workers.tasks.fetch_emails_for_user")
def fetch_emails_for_user(user_id: str):
    asyncio.run(_fetch_emails_for_user_async(user_id))


async def _fetch_emails_for_user_async(user_id: str):
    SessionLocal = _create_session_factory()
    async with SessionLocal() as db:
        result = await db.execute(
            select(User).where(User.id == user_id)
        )
        user = result.scalar_one_or_none()

        if not user:
            logger.error("user_not_found", user_id=user_id)
            return

        gmail_service = GmailService(user.encrypted_oauth_tokens)

        try:
            email_data_list = await gmail_service.fetch_recent_emails(
                max_results=settings.MAX_EMAILS_PER_FETCH,
                query="is:unread"
            )

            for email_data in email_data_list:
                existing = await db.execute(
                    select(Email).where(
                        Email.gmail_message_id == email_data["gmail_message_id"]
                    ).where(
                        Email.user_id == user_id
                    )
                )

                if existing.scalar_one_or_none():
                    continue

                email = Email(
                    user_id=user_id,
                    **email_data
                )
                db.add(email)
                await db.commit()
                await db.refresh(email)

                celery_app.send_task(
                    "workers.tasks.classify_email",
                    args=[str(email.id)]
                )

                celery_app.send_task(
                    "workers.tasks.create_embedding",
                    args=[str(email.id), user_id]
                )

            logger.info("emails_fetched_for_user", user_id=user_id, count=len(email_data_list))

        except Exception as e:
            logger.error("email_fetch_failed", user_id=user_id, error=str(e))


@celery_app.task(name="workers.tasks.fetch_emails_for_all_users")
def fetch_emails_for_all_users():
    asyncio.run(_fetch_emails_for_all_users_async())


async def _fetch_emails_for_all_users_async():
    SessionLocal = _create_session_factory()
    async with SessionLocal() as db:
        result = await db.execute(select(User))
        users = result.scalars().all()

        for user in users:
            celery_app.send_task(
                "workers.tasks.fetch_emails_for_user",
                args=[str(user.id)]
            )

        logger.info("scheduled_email_fetch_for_all_users", user_count=len(users))


@celery_app.task(name="workers.tasks.classify_email")
def classify_email(email_id: str):
    asyncio.run(_classify_email_async(email_id))


async def _classify_email_async(email_id: str):
    SessionLocal = _create_session_factory()
    async with SessionLocal() as db:
        classification_service = ClassificationService(db)

        try:
            classification = await classification_service.classify_email(email_id)

            result = await db.execute(
                select(Email).where(Email.id == email_id)
            )
            email = result.scalar_one_or_none()

            if email:
                category = classification.get("category", "").lower()
                subject = (email.subject or "").lower()
                meeting_keywords = ["meeting", "schedule", "calendar", "reschedule", "appointment", "call", "sync"]
                has_meeting_signal = (
                    category == "meeting" or
                    any(kw in subject for kw in meeting_keywords) or
                    any(kw in (email.body or "").lower()[:500] for kw in meeting_keywords)
                )

                if has_meeting_signal:
                    # Calendar pipeline handles both the event and the reply suggestion
                    celery_app.send_task(
                        "workers.tasks.process_calendar_event",
                        args=[email_id, str(email.user_id)]
                    )
                elif classification.get("needs_response"):
                    # Non-meeting emails get a generic suggestion
                    celery_app.send_task(
                        "workers.tasks.create_suggestion",
                        args=[email_id, str(email.user_id)]
                    )

                # Always check if this is a response to a pending meeting proposal
                celery_app.send_task(
                    "workers.tasks.check_meeting_response",
                    args=[email_id, str(email.user_id)]
                )

            logger.info("email_classified_task", email_id=email_id)

        except Exception as e:
            logger.error("classification_task_failed", email_id=email_id, error=str(e))


@celery_app.task(name="workers.tasks.create_embedding")
def create_embedding(email_id: str, user_id: str):
    asyncio.run(_create_embedding_async(email_id, user_id))


async def _create_embedding_async(email_id: str, user_id: str):
    SessionLocal = _create_session_factory()
    async with SessionLocal() as db:
        memory_service = MemoryService(db)

        try:
            await memory_service.create_embedding(email_id, user_id)
            logger.info("embedding_created_task", email_id=email_id)

        except Exception as e:
            logger.error("embedding_task_failed", email_id=email_id, error=str(e))


@celery_app.task(name="workers.tasks.create_suggestion")
def create_suggestion(email_id: str, user_id: str):
    asyncio.run(_create_suggestion_async(email_id, user_id))


async def _create_suggestion_async(email_id: str, user_id: str):
    SessionLocal = _create_session_factory()
    async with SessionLocal() as db:
        suggestion_service = SuggestionService(db)

        try:
            suggestion = await suggestion_service.create_suggestion(email_id, user_id)
            logger.info(
                "suggestion_created_task",
                suggestion_id=str(suggestion.id),
                confidence=suggestion.confidence_score
            )

        except Exception as e:
            logger.error("suggestion_task_failed", email_id=email_id, error=str(e))


@celery_app.task(name="workers.tasks.rebuild_style_profile")
def rebuild_style_profile(user_id: str):
    asyncio.run(_rebuild_style_profile_async(user_id))


async def _rebuild_style_profile_async(user_id: str):
    SessionLocal = _create_session_factory()
    async with SessionLocal() as db:
        style_service = StyleService(db)

        try:
            profile = await style_service.build_style_profile(user_id)
            logger.info("style_profile_rebuilt_task", user_id=user_id, version=profile.version)

        except Exception as e:
            logger.error("style_profile_task_failed", user_id=user_id, error=str(e))


@celery_app.task(name="workers.tasks.process_calendar_event")
def process_calendar_event(email_id: str, user_id: str):
    asyncio.run(_process_calendar_event_async(email_id, user_id))


async def _process_calendar_event_async(email_id: str, user_id: str):
    SessionLocal = _create_session_factory()
    async with SessionLocal() as db:
        calendar_service = CalendarService(db)

        try:
            # dry_run=True: extract meeting details and check conflicts,
            # but do NOT create the calendar event — wait for user approval
            result = await calendar_service.process_email_for_calendar(email_id, user_id, dry_run=True)
            logger.info(
                "calendar_event_processed_task",
                email_id=email_id,
                has_meeting=result.get("has_meeting"),
                action=result.get("action")
            )

            # Generate a calendar-aware reply suggestion (user must approve before event is created)
            calendar_context = result.get("calendar_context")
            if result.get("has_meeting") and calendar_context:
                suggestion_service = SuggestionService(db)
                suggestion = await suggestion_service.create_calendar_suggestion(
                    email_id=email_id,
                    user_id=user_id,
                    calendar_context=calendar_context,
                )
                logger.info(
                    "calendar_suggestion_created_task",
                    email_id=email_id,
                    suggestion_id=str(suggestion.id),
                    has_conflict=calendar_context.get("has_conflict"),
                )

        except Exception as e:
            logger.error("calendar_task_failed", email_id=email_id, error=str(e))


@celery_app.task(name="workers.tasks.check_meeting_response")
def check_meeting_response(email_id: str, user_id: str):
    asyncio.run(_check_meeting_response_async(email_id, user_id))


async def _check_meeting_response_async(email_id: str, user_id: str):
    """Check if an incoming email is a positive response to a pending meeting proposal.

    Looks up Redis for pending proposals where the sender matches a recipient
    we previously emailed. Uses the LLM to detect if the response is positive.
    If so, auto-creates a Google Calendar event.
    """
    import json as _json
    import redis.asyncio as aioredis

    SessionLocal = _create_session_factory()
    async with SessionLocal() as db:
        try:
            result = await db.execute(
                select(Email).where(Email.id == email_id)
            )
            email = result.scalar_one_or_none()
            if not email:
                return

            # Extract sender email (handle "Name <email>" format)
            sender = email.sender or ""
            import re
            match = re.search(r'[\w.+-]+@[\w-]+\.[\w.-]+', sender)
            sender_email = match.group(0).lower() if match else sender.lower()

            # Check Redis for pending meeting proposals for this sender
            r = aioredis.from_url(settings.REDIS_URL, decode_responses=True)
            key = f"pending_meeting:{user_id}:{sender_email}"
            proposal_json = await r.get(key)

            if not proposal_json:
                await r.aclose()
                return

            proposal = _json.loads(proposal_json)
            logger.info("pending_meeting_found", email_id=email_id, sender=sender_email,
                        title=proposal.get("title"))

            # Use LLM to check if this is a positive response
            from services.llm_router import llm_router

            body_preview = (email.body or "")[:500]
            positive_check = await llm_router.detect_meeting_acceptance(
                email_body=body_preview,
                original_subject=proposal.get("subject", ""),
                proposed_meeting=proposal.get("title", ""),
            )

            if not positive_check.get("accepted"):
                logger.info("meeting_response_not_positive", email_id=email_id)
                await r.aclose()
                return

            logger.info("positive_meeting_response_detected", email_id=email_id,
                        sender=sender_email, title=proposal.get("title"))

            # Auto-create the calendar event
            user_result = await db.execute(
                select(User).where(User.id == user_id)
            )
            user = user_result.scalar_one_or_none()
            if not user:
                await r.aclose()
                return

            from tools.calendar_tool import CalendarTool

            calendar_tool = CalendarTool(user.encrypted_oauth_tokens, user_id)
            user_timezone = getattr(user, 'timezone', 'Asia/Karachi')

            extraction = {
                "has_meeting": True,
                "action": "create",
                "title": proposal.get("title"),
                "date": proposal.get("date"),
                "time": proposal.get("time"),
                "duration_minutes": proposal.get("duration_minutes", 60),
                "attendees": proposal.get("attendees", []),
                "location": proposal.get("location"),
                "notes": f"Auto-created after positive response from {sender_email}",
            }

            calendar_service = CalendarService(db)
            cal_result = await calendar_service._create_meeting(
                calendar_tool=calendar_tool,
                extraction=extraction,
                email_id=email_id,
                user_id=user_id,
                user_timezone=user_timezone,
                dry_run=False,
                user_email=user.email,
            )

            if cal_result.get("action") == "create" and cal_result.get("calendar_event"):
                evt = cal_result["calendar_event"]
                logger.info("auto_calendar_from_response",
                            email_id=email_id,
                            summary=evt.summary,
                            sender=sender_email)

                # Create a notification for the user
                from models.notification import Notification
                notification = Notification(
                    user_id=user_id,
                    type="calendar_auto_created",
                    source="echo",
                    title=f"Meeting confirmed: {evt.summary}",
                    message=f"{sender_email} confirmed — calendar event created automatically",
                    extra_data={
                        "email_id": email_id,
                        "calendar_event_summary": evt.summary,
                        "google_event_id": evt.google_event_id,
                    },
                )
                db.add(notification)
                await db.commit()

                # Remove the pending proposal from Redis
                await r.delete(key)
            elif cal_result.get("action") == "already_scheduled":
                logger.info("auto_calendar_already_exists", email_id=email_id)
                await r.delete(key)

            await r.aclose()

        except Exception as e:
            logger.error("check_meeting_response_failed", email_id=email_id, error=str(e))


@celery_app.task(name="workers.tasks.reset_daily_token_budgets")
def reset_daily_token_budgets():
    asyncio.run(_reset_daily_token_budgets_async())


async def _reset_daily_token_budgets_async():
    SessionLocal = _create_session_factory()
    async with SessionLocal() as db:
        await db.execute(
            update(User).values(tokens_used_today=0)
        )
        await db.commit()

        logger.info("daily_token_budgets_reset")


@celery_app.task(name="workers.tasks.generate_digest_for_user")
def generate_digest_for_user(user_id: str):
    asyncio.run(_generate_digest_for_user_async(user_id))


async def _generate_digest_for_user_async(user_id: str):
    SessionLocal = _create_session_factory()
    async with SessionLocal() as db:
        digest_service = DigestService(db)

        try:
            digest = await digest_service.generate_digest(user_id)
            logger.info(
                "digest_generated_task",
                user_id=user_id,
                digest_date=str(digest.digest_date),
                total_emails=digest.content.get("total_emails", 0),
            )
        except Exception as e:
            logger.error("digest_generation_failed", user_id=user_id, error=str(e))


@celery_app.task(name="workers.tasks.generate_digests_for_all_users")
def generate_digests_for_all_users():
    asyncio.run(_generate_digests_for_all_users_async())


async def _generate_digests_for_all_users_async():
    SessionLocal = _create_session_factory()
    async with SessionLocal() as db:
        result = await db.execute(select(User))
        users = result.scalars().all()

        for user in users:
            celery_app.send_task(
                "workers.tasks.generate_digest_for_user",
                args=[str(user.id)]
            )

        logger.info("scheduled_digest_generation_for_all_users", user_count=len(users))


@celery_app.task(name="workers.tasks.check_deadline_reminders")
def check_deadline_reminders():
    asyncio.run(_check_deadline_reminders_async())


async def _check_deadline_reminders_async():
    from models.task import Task
    from models.notification import Notification
    from datetime import datetime, timedelta

    SessionLocal = _create_session_factory()
    async with SessionLocal() as db:
        try:
            now = datetime.utcnow()
            cutoff = now + timedelta(hours=24)

            # Find tasks with approaching or past deadlines that aren't completed/dismissed
            result = await db.execute(
                select(Task).where(
                    Task.due_date.isnot(None),
                    Task.due_date <= cutoff,
                    Task.status.notin_(["completed", "dismissed"]),
                )
            )
            tasks = result.scalars().all()

            if not tasks:
                logger.info("deadline_check_no_tasks")
                return

            created = 0
            for task in tasks:
                is_overdue = task.due_date.replace(tzinfo=None) < now if task.due_date.tzinfo else task.due_date < now
                notif_type = "deadline_overdue" if is_overdue else "deadline_reminder"

                # Check if we already sent a reminder for this task recently (within 12h)
                existing = await db.execute(
                    select(Notification).where(
                        Notification.user_id == task.user_id,
                        Notification.type == notif_type,
                        Notification.created_at >= now - timedelta(hours=12),
                        Notification.extra_data["task_id"].astext == str(task.id),
                    )
                )
                if existing.scalar_one_or_none():
                    continue

                project_name = (task.extra_data or {}).get("project_name", "")
                title_prefix = "Task overdue" if is_overdue else "Task deadline approaching"
                due_str = task.due_date.strftime("%b %d at %I:%M %p")

                notification = Notification(
                    user_id=task.user_id,
                    type=notif_type,
                    source=task.source,
                    title=f"{title_prefix}: {task.title}",
                    message=f"Due: {due_str}" + (f" ({project_name})" if project_name else ""),
                    extra_data={
                        "task_id": str(task.id),
                        "due_date": task.due_date.isoformat(),
                        "project_name": project_name,
                        "is_overdue": is_overdue,
                    },
                )
                db.add(notification)
                created += 1

            if created:
                await db.commit()

            logger.info("deadline_reminders_checked", tasks_found=len(tasks), notifications_created=created)

        except Exception as e:
            logger.error("deadline_reminder_failed", error=str(e))


# ─── Google Drive Scanning Tasks ─────────────────────────────────────────────


@celery_app.task(name="workers.tasks.scan_drive_for_user")
def scan_drive_for_user(user_id: str):
    asyncio.run(_scan_drive_for_user_async(user_id))


async def _scan_drive_for_user_async(user_id: str):
    from models.drive_document import DriveDocument
    from services.drive_service import DriveService
    from services.document_service import DocumentService
    from datetime import datetime
    import uuid

    SessionLocal = _create_session_factory()
    async with SessionLocal() as db:
        result = await db.execute(
            select(User).where(User.id == user_id)
        )
        user = result.scalar_one_or_none()

        if not user or not user.encrypted_oauth_tokens:
            logger.warning("drive_scan_skip_no_tokens", user_id=user_id)
            return

        drive_service = DriveService(user.encrypted_oauth_tokens)

        try:
            # Determine last scan time for incremental scanning
            last_scan_result = await db.execute(
                select(DriveDocument.last_indexed_at)
                .where(DriveDocument.user_id == user_id)
                .where(DriveDocument.last_indexed_at.isnot(None))
                .order_by(DriveDocument.last_indexed_at.desc())
                .limit(1)
            )
            last_scan_row = last_scan_result.scalar_one_or_none()
            # Add a 10-minute buffer to avoid missing files at the boundary
            if last_scan_row:
                from datetime import timedelta
                buffered_time = last_scan_row - timedelta(minutes=10)
                modified_after = buffered_time.isoformat()
            else:
                modified_after = None

            # List files from Drive
            drive_files = await drive_service.list_files(modified_after=modified_after)

            new_count = 0
            updated_count = 0
            skipped_count = 0

            drive_file_ids_seen = set()

            for file_data in drive_files:
                file_id = file_data["id"]
                mime_type = file_data.get("mimeType", "")
                drive_file_ids_seen.add(file_id)

                # Skip non-indexable files
                if not DriveService.is_indexable(mime_type):
                    skipped_count += 1
                    continue

                # Skip files that are too large
                file_size = int(file_data.get("size", 0) or 0)
                max_bytes = settings.DRIVE_MAX_FILE_SIZE_MB * 1024 * 1024
                if file_size > max_bytes:
                    skipped_count += 1
                    continue

                # Check if already indexed
                existing_result = await db.execute(
                    select(DriveDocument).where(
                        DriveDocument.user_id == user_id,
                        DriveDocument.drive_file_id == file_id,
                    )
                )
                existing_doc = existing_result.scalar_one_or_none()

                modified_time = file_data.get("modifiedTime", "")
                owners = file_data.get("owners", [])
                owner_email = owners[0].get("emailAddress", "") if owners else ""

                if existing_doc:
                    # Check if modified since last index
                    if existing_doc.drive_modified_at and modified_time:
                        from datetime import timezone
                        drive_mod = datetime.fromisoformat(modified_time.replace("Z", "+00:00"))
                        last_mod = existing_doc.drive_modified_at
                        if last_mod.tzinfo is None:
                            last_mod = last_mod.replace(tzinfo=timezone.utc)
                        if drive_mod <= last_mod:
                            continue  # Not modified, skip

                    existing_doc.name = file_data.get("name", existing_doc.name)
                    existing_doc.drive_modified_at = datetime.fromisoformat(modified_time.replace("Z", "+00:00")) if modified_time else None
                    existing_doc.status = "pending"
                    await db.commit()
                    updated_count += 1
                else:
                    # New file
                    created_time = file_data.get("createdTime", "")
                    new_doc = DriveDocument(
                        id=uuid.uuid4(),
                        user_id=user_id,
                        drive_file_id=file_id,
                        name=file_data.get("name", "Untitled"),
                        mime_type=mime_type,
                        drive_link=file_data.get("webViewLink", ""),
                        owner_email=owner_email,
                        file_size=file_size if file_size else None,
                        drive_created_at=datetime.fromisoformat(created_time.replace("Z", "+00:00")) if created_time else None,
                        drive_modified_at=datetime.fromisoformat(modified_time.replace("Z", "+00:00")) if modified_time else None,
                        status="pending",
                        extra_data={"parents": file_data.get("parents", [])},
                    )
                    db.add(new_doc)
                    await db.commit()
                    new_count += 1

                # Dispatch indexing task
                celery_app.send_task(
                    "workers.tasks.index_document_task",
                    args=[user_id, file_id],
                )

            # Mark deleted files (in DB but no longer in Drive)
            if not modified_after:
                # Only do full delete detection on full scans
                all_docs_result = await db.execute(
                    select(DriveDocument).where(
                        DriveDocument.user_id == user_id,
                        DriveDocument.status != "deleted",
                    )
                )
                all_docs = all_docs_result.scalars().all()
                deleted_count = 0
                for doc in all_docs:
                    if doc.drive_file_id not in drive_file_ids_seen:
                        doc.status = "deleted"
                        deleted_count += 1
                if deleted_count:
                    await db.commit()
                    logger.info("drive_docs_marked_deleted", user_id=user_id, count=deleted_count)

            logger.info(
                "drive_scan_completed",
                user_id=user_id,
                new=new_count,
                updated=updated_count,
                skipped=skipped_count,
                total_files=len(drive_files),
            )

        except Exception as e:
            logger.error("drive_scan_failed", user_id=user_id, error=str(e))


@celery_app.task(name="workers.tasks.index_document_task")
def index_document_task(user_id: str, drive_file_id: str):
    asyncio.run(_index_document_task_async(user_id, drive_file_id))


async def _index_document_task_async(user_id: str, drive_file_id: str):
    from services.drive_service import DriveService
    from services.document_service import DocumentService

    SessionLocal = _create_session_factory()
    async with SessionLocal() as db:
        result = await db.execute(
            select(User).where(User.id == user_id)
        )
        user = result.scalar_one_or_none()

        if not user or not user.encrypted_oauth_tokens:
            logger.warning("index_doc_skip_no_tokens", user_id=user_id)
            return

        drive_service = DriveService(user.encrypted_oauth_tokens)
        doc_service = DocumentService()

        try:
            doc = await doc_service.index_document(db, user_id, drive_file_id, drive_service)
            logger.info(
                "document_indexed_task",
                drive_file_id=drive_file_id,
                name=doc.name,
                chunks=doc.chunk_count,
            )
        except Exception as e:
            logger.error("document_index_task_failed", drive_file_id=drive_file_id, error=str(e))


@celery_app.task(name="workers.tasks.scan_drive_for_all_users")
def scan_drive_for_all_users():
    asyncio.run(_scan_drive_for_all_users_async())


async def _scan_drive_for_all_users_async():
    SessionLocal = _create_session_factory()
    async with SessionLocal() as db:
        result = await db.execute(
            select(User).where(User.encrypted_oauth_tokens.isnot(None))
        )
        users = result.scalars().all()

        for user in users:
            celery_app.send_task(
                "workers.tasks.scan_drive_for_user",
                args=[str(user.id)],
            )

        logger.info("scheduled_drive_scan_for_all_users", user_count=len(users))
