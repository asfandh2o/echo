from typing import Optional, Dict, Any, List
from datetime import datetime, date, timedelta, timezone
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, and_
from models.digest import Digest
from models.email import Email
from models.suggestion import Suggestion
from services.llm_router import llm_router
from core.logging import get_logger

logger = get_logger(__name__)


class DigestService:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def generate_digest(self, user_id: str, for_date: date = None) -> Digest:
        """Generate or regenerate a digest for the given user and date."""
        if for_date is None:
            for_date = date.today()

        period_end = datetime.combine(for_date, datetime.min.time(), tzinfo=timezone.utc).replace(hour=6)
        period_start = period_end - timedelta(hours=24)

        existing = await self._get_existing_digest(user_id, for_date)
        if existing and existing.status == "generating":
            return existing

        email_stats = await self._gather_email_stats(user_id, period_start, period_end)
        suggestion_stats = await self._gather_suggestion_stats(user_id, period_start, period_end)
        urgent_emails = await self._gather_urgent_emails(user_id, period_start, period_end)

        content = {
            "total_emails": email_stats["total"],
            "category_breakdown": email_stats["categories"],
            "urgent_emails": urgent_emails,
            "suggestions_summary": suggestion_stats,
            "period_start": period_start.isoformat(),
            "period_end": period_end.isoformat(),
        }

        llm_summary = await self._generate_llm_summary(content)

        if existing:
            existing.content = content
            existing.llm_summary = llm_summary
            existing.status = "completed"
            await self.db.commit()
            await self.db.refresh(existing)
            logger.info("digest_updated", user_id=user_id, date=str(for_date))
            return existing

        digest = Digest(
            user_id=user_id,
            digest_date=for_date,
            content=content,
            llm_summary=llm_summary,
            status="completed",
        )
        self.db.add(digest)
        await self.db.commit()
        await self.db.refresh(digest)
        logger.info("digest_created", user_id=user_id, date=str(for_date))
        return digest

    async def get_latest_digest(self, user_id: str) -> Optional[Digest]:
        result = await self.db.execute(
            select(Digest)
            .where(Digest.user_id == user_id)
            .order_by(Digest.digest_date.desc())
            .limit(1)
        )
        return result.scalar_one_or_none()

    async def get_digest_by_date(self, user_id: str, for_date: date) -> Optional[Digest]:
        result = await self.db.execute(
            select(Digest).where(
                and_(Digest.user_id == user_id, Digest.digest_date == for_date)
            )
        )
        return result.scalar_one_or_none()

    async def list_digests(self, user_id: str, limit: int = 7) -> List[Digest]:
        result = await self.db.execute(
            select(Digest)
            .where(Digest.user_id == user_id)
            .order_by(Digest.digest_date.desc())
            .limit(limit)
        )
        return result.scalars().all()

    async def _get_existing_digest(self, user_id: str, for_date: date) -> Optional[Digest]:
        result = await self.db.execute(
            select(Digest).where(
                and_(Digest.user_id == user_id, Digest.digest_date == for_date)
            )
        )
        return result.scalar_one_or_none()

    async def _gather_email_stats(self, user_id: str, start: datetime, end: datetime) -> Dict[str, Any]:
        total_result = await self.db.execute(
            select(func.count(Email.id)).where(
                and_(
                    Email.user_id == user_id,
                    Email.received_at >= start,
                    Email.received_at < end,
                )
            )
        )
        total = total_result.scalar() or 0

        classifications_result = await self.db.execute(
            select(Email.classification).where(
                and_(
                    Email.user_id == user_id,
                    Email.received_at >= start,
                    Email.received_at < end,
                    Email.classification.isnot(None),
                )
            )
        )
        classifications = classifications_result.scalars().all()

        categories = {}
        for c in classifications:
            if c and isinstance(c, dict):
                cat = c.get("category", "uncategorized").lower()
                categories[cat] = categories.get(cat, 0) + 1

        return {"total": total, "categories": categories}

    async def _gather_suggestion_stats(self, user_id: str, start: datetime, end: datetime) -> Dict[str, Any]:
        result = await self.db.execute(
            select(Suggestion.status, Suggestion.feedback_type, func.count(Suggestion.id))
            .where(
                and_(
                    Suggestion.user_id == user_id,
                    Suggestion.created_at >= start,
                    Suggestion.created_at < end,
                )
            )
            .group_by(Suggestion.status, Suggestion.feedback_type)
        )
        rows = result.all()

        stats = {"total": 0, "accepted": 0, "rejected": 0, "pending": 0}
        for status_val, feedback_type, count in rows:
            stats["total"] += count
            if status_val == "pending":
                stats["pending"] += count
            elif feedback_type == "accepted":
                stats["accepted"] += count
            elif feedback_type in ("rejected", "edited"):
                stats["rejected"] += count

        return stats

    async def _gather_urgent_emails(self, user_id: str, start: datetime, end: datetime) -> List[Dict[str, Any]]:
        result = await self.db.execute(
            select(Email).where(
                and_(
                    Email.user_id == user_id,
                    Email.received_at >= start,
                    Email.received_at < end,
                )
            ).order_by(Email.received_at.desc())
        )
        emails = result.scalars().all()

        urgent_list = []
        for email in emails:
            if email.classification and email.classification.get("urgent"):
                sugg_result = await self.db.execute(
                    select(func.count(Suggestion.id)).where(
                        and_(
                            Suggestion.email_id == email.id,
                            Suggestion.status == "pending",
                        )
                    )
                )
                has_pending = (sugg_result.scalar() or 0) > 0

                urgent_list.append({
                    "id": str(email.id),
                    "subject": email.subject,
                    "sender": email.sender,
                    "received_at": email.received_at.isoformat() if email.received_at else "",
                    "has_pending_suggestion": has_pending,
                })

        return urgent_list

    async def _generate_llm_summary(self, content: Dict[str, Any]) -> str:
        try:
            summary = await llm_router.generate_digest_summary(content)
            return summary
        except Exception as e:
            logger.error("digest_llm_summary_failed", error=str(e))
            total = content.get("total_emails", 0)
            urgent_count = len(content.get("urgent_emails", []))
            pending = content.get("suggestions_summary", {}).get("pending", 0)
            return (
                f"You received {total} emails in the last 24 hours. "
                f"{urgent_count} are urgent and need attention. "
                f"{pending} reply suggestions are waiting for your review."
            )
