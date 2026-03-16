from typing import Dict, Any
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from models.email import Email
from services.llm_router import llm_router
from core.logging import get_logger
import json

logger = get_logger(__name__)


class ClassificationService:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def classify_email(self, email_id: str) -> Dict[str, Any]:
        result = await self.db.execute(
            select(Email).where(Email.id == email_id)
        )
        email = result.scalar_one_or_none()

        if not email:
            raise ValueError(f"Email {email_id} not found")

        if email.classification:
            logger.info("email_already_classified", email_id=email_id)
            return email.classification

        classification = await llm_router.classify_email(
            email_content=email.body,
            subject=email.subject,
            sender=email.sender
        )

        email.classification = classification
        await self.db.commit()

        logger.info(
            "email_classified_and_saved",
            email_id=email_id,
            category=classification.get("category"),
            needs_response=classification.get("needs_response")
        )

        return classification

    async def bulk_classify(self, user_id: str, limit: int = 50) -> int:
        result = await self.db.execute(
            select(Email)
            .where(Email.user_id == user_id)
            .where(Email.classification.is_(None))
            .limit(limit)
        )
        emails = result.scalars().all()

        classified_count = 0
        for email in emails:
            try:
                await self.classify_email(str(email.id))
                classified_count += 1
            except Exception as e:
                logger.error("classification_failed", email_id=str(email.id), error=str(e))

        logger.info("bulk_classification_complete", count=classified_count)
        return classified_count
