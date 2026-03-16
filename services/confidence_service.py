from typing import Dict, Any
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from models.suggestion import Suggestion
from models.feedback_log import FeedbackLog
from core.config import settings
from core.logging import get_logger

logger = get_logger(__name__)


class ConfidenceService:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def calculate_confidence(
        self,
        user_id: str,
        classification_confidence: float,
        style_similarity: float,
        context_quality: float
    ) -> float:
        historical_acceptance = await self._get_historical_acceptance_rate(user_id)

        weights = {
            "classification": 0.25,
            "historical": 0.35,
            "style": 0.25,
            "context": 0.15
        }

        confidence = (
            weights["classification"] * classification_confidence +
            weights["historical"] * historical_acceptance +
            weights["style"] * style_similarity +
            weights["context"] * context_quality
        )

        confidence = max(0.0, min(1.0, confidence))

        logger.info(
            "confidence_calculated",
            user_id=user_id,
            confidence=confidence,
            historical_acceptance=historical_acceptance
        )

        return confidence

    async def _get_historical_acceptance_rate(self, user_id: str) -> float:
        from sqlalchemy import case, literal

        try:
            result = await self.db.execute(
                select(
                    func.count(FeedbackLog.id).label("total"),
                    func.sum(
                        case(
                            (FeedbackLog.feedback_type.in_(["accepted", "edited"]), literal(1)),
                            else_=literal(0)
                        )
                    ).label("accepted")
                )
                .where(FeedbackLog.user_id == user_id)
            )

            row = result.first()

            if not row or not row.total or row.total == 0:
                return 0.5

            acceptance_rate = row.accepted / row.total
            return acceptance_rate
        except Exception as e:
            logger.warning("historical_acceptance_query_failed", error=str(e))
            return 0.5

    async def get_action_recommendation(self, confidence_score: float, user_autonomy: str) -> str:
        if user_autonomy == "supervised":
            return "require_approval"

        if confidence_score >= settings.AUTO_SEND_THRESHOLD:
            return "auto_send"
        elif confidence_score >= settings.APPROVAL_THRESHOLD:
            return "require_approval"
        elif confidence_score >= settings.SUGGESTION_THRESHOLD:
            return "show_suggestion"
        else:
            return "skip"

    async def assess_risk_level(self, email_content: str, draft_content: str) -> str:
        financial_keywords = ["payment", "invoice", "transfer", "wire", "bank", "account", "$", "€", "£"]
        legal_keywords = ["contract", "agreement", "legal", "lawsuit", "attorney", "court"]
        commitment_keywords = ["promise", "guarantee", "commit", "deadline", "deliver by"]

        content_lower = (email_content + " " + draft_content).lower()

        financial_count = sum(1 for kw in financial_keywords if kw in content_lower)
        legal_count = sum(1 for kw in legal_keywords if kw in content_lower)
        commitment_count = sum(1 for kw in commitment_keywords if kw in content_lower)

        if financial_count >= 2 or legal_count >= 2:
            return "high"
        elif commitment_count >= 2 or financial_count >= 1 or legal_count >= 1:
            return "medium"
        else:
            return "low"
