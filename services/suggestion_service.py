from typing import Dict, Any, List, Optional
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, desc
from models.suggestion import Suggestion
from models.email import Email
from models.feedback_log import FeedbackLog
from services.llm_router import llm_router
from services.memory_service import MemoryService
from services.style_service import StyleService
from services.confidence_service import ConfidenceService
from services.contact_service import ContactService
from services.gmail_service import GmailService
from core.logging import get_logger
import difflib

logger = get_logger(__name__)


class SuggestionService:
    def __init__(self, db: AsyncSession):
        self.db = db
        self.memory_service = MemoryService(db)
        self.style_service = StyleService(db)
        self.confidence_service = ConfidenceService(db)
        self.contact_service = ContactService(db)

    async def create_suggestion(self, email_id: str, user_id: str) -> Suggestion:
        result = await self.db.execute(
            select(Email).where(Email.id == email_id)
        )
        email = result.scalar_one_or_none()

        if not email:
            raise ValueError(f"Email {email_id} not found")

        thread_context = await self._get_thread_context(email.thread_id, user_id)

        similar_emails = await self.memory_service.find_similar_emails(
            query_text=f"{email.subject}\n{email.body}",
            user_id=user_id,
            top_k=5
        )

        style_profile = await self.style_service.get_style_profile(user_id)

        contact_context = await self.contact_service.get_contact_context(email.sender, user_id)

        # Search for relevant company documents from Google Drive
        doc_context = []
        try:
            from services.document_service import DocumentService
            doc_service = DocumentService()
            doc_context = await doc_service.search_documents(
                db=self.db,
                user_id=user_id,
                query=f"{email.subject} {email.body[:500]}",
                limit=3,
            )
        except Exception as e:
            logger.warning("document_search_failed_in_suggestion", error=str(e))

        draft_result = await llm_router.draft_reply(
            email_content=email.body,
            thread_context=[ctx["body"] for ctx in thread_context],
            similar_emails=[se["body"] for se in similar_emails],
            style_profile=style_profile,
            contact_context=contact_context,
            document_context=doc_context,
        )

        verification = await llm_router.verify_reply(
            original_email=email.body,
            drafted_reply=draft_result.get("draft", "")
        )

        if not verification.get("safe", False):
            draft_result["confidence"] = min(draft_result.get("confidence", 0.5), 0.4)
            draft_result["draft"] = f"[DRAFT FLAGGED - REQUIRES REVIEW]\n\n{draft_result.get('draft', '')}"

        style_similarity = 0.8 if similar_emails else 0.5
        context_quality = min(len(thread_context) / 5, 1.0)

        confidence = await self.confidence_service.calculate_confidence(
            user_id=user_id,
            classification_confidence=email.classification.get("confidence", 0.5) if email.classification else 0.5,
            style_similarity=style_similarity,
            context_quality=context_quality
        )

        suggestion = Suggestion(
            email_id=email_id,
            user_id=user_id,
            suggestion_text=draft_result.get("draft", ""),
            confidence_score=confidence,
            reasoning=draft_result.get("reasoning", ""),
            status="pending",
            context_used={
                "thread_messages": len(thread_context),
                "similar_emails": len(similar_emails),
                "documents_used": len(doc_context),
                "verification": verification,
                "risk_level": verification.get("risk_level", "unknown")
            }
        )

        self.db.add(suggestion)
        await self.db.commit()
        await self.db.refresh(suggestion)

        logger.info(
            "suggestion_created",
            suggestion_id=str(suggestion.id),
            confidence=confidence,
            risk_level=verification.get("risk_level")
        )

        return suggestion

    async def create_calendar_suggestion(
        self,
        email_id: str,
        user_id: str,
        calendar_context: Dict[str, Any],
    ) -> Suggestion:
        """Create a suggestion that's aware of the user's calendar availability."""
        result = await self.db.execute(
            select(Email).where(Email.id == email_id)
        )
        email = result.scalar_one_or_none()

        if not email:
            raise ValueError(f"Email {email_id} not found")

        style_profile = await self.style_service.get_style_profile(user_id)

        contact_context = await self.contact_service.get_contact_context(email.sender, user_id)

        draft_result = await llm_router.draft_calendar_aware_reply(
            email_content=email.body,
            subject=email.subject,
            sender=email.sender,
            calendar_context=calendar_context,
            style_profile=style_profile,
            contact_context=contact_context,
        )

        has_conflict = calendar_context.get("has_conflict", False)
        confidence = draft_result.get("confidence", 0.7)
        # Higher confidence when we have clear calendar data to work with
        if has_conflict and calendar_context.get("free_slots"):
            confidence = max(confidence, 0.75)

        suggestion = Suggestion(
            email_id=email_id,
            user_id=user_id,
            suggestion_text=draft_result.get("draft", ""),
            confidence_score=confidence,
            reasoning=draft_result.get("reasoning", ""),
            status="pending",
            context_used={
                "type": "calendar_aware",
                "has_conflict": has_conflict,
                "suggested_times": draft_result.get("suggested_times", []),
                "proposed_meeting": calendar_context.get("proposed_meeting", {}),
            }
        )

        self.db.add(suggestion)
        await self.db.commit()
        await self.db.refresh(suggestion)

        logger.info(
            "calendar_suggestion_created",
            suggestion_id=str(suggestion.id),
            email_id=email_id,
            has_conflict=has_conflict,
            confidence=confidence,
        )

        return suggestion

    async def submit_feedback(
        self,
        suggestion_id: str,
        user_id: str,
        feedback_type: str,
        final_text: Optional[str] = None
    ) -> FeedbackLog:
        result = await self.db.execute(
            select(Suggestion).where(Suggestion.id == suggestion_id)
        )
        suggestion = result.scalar_one_or_none()

        if not suggestion:
            raise ValueError(f"Suggestion {suggestion_id} not found")

        if str(suggestion.user_id) != user_id:
            raise ValueError("Unauthorized access to suggestion")

        if final_text is None:
            final_text = suggestion.suggestion_text

        diff_score = self._calculate_diff_score(suggestion.suggestion_text, final_text)

        suggestion.feedback_type = feedback_type
        suggestion.final_text = final_text
        suggestion.status = "completed"

        feedback_log = FeedbackLog(
            user_id=user_id,
            suggestion_id=suggestion_id,
            feedback_type=feedback_type,
            diff_score=diff_score,
            original_text=suggestion.suggestion_text,
            final_text=final_text
        )

        self.db.add(feedback_log)
        await self.db.commit()

        # Trigger style learning from user edits
        if feedback_type in ("edited", "rejected") and diff_score < 0.95:
            try:
                await self.style_service.apply_feedback_learning(user_id)
            except Exception as e:
                logger.warning("feedback_style_learning_failed", error=str(e))

        logger.info(
            "feedback_submitted",
            suggestion_id=suggestion_id,
            feedback_type=feedback_type,
            diff_score=diff_score
        )

        return feedback_log

    def _calculate_diff_score(self, original: str, final: str) -> float:
        if not original or not final:
            return 0.0

        similarity = difflib.SequenceMatcher(None, original, final).ratio()
        return similarity

    async def _get_thread_context(self, thread_id: str, user_id: str) -> List[Dict[str, Any]]:
        result = await self.db.execute(
            select(Email)
            .where(Email.thread_id == thread_id)
            .where(Email.user_id == user_id)
            .order_by(desc(Email.received_at))
            .limit(5)
        )
        emails = result.scalars().all()

        return [
            {
                "subject": email.subject,
                "sender": email.sender,
                "body": email.body,
                "received_at": email.received_at
            }
            for email in emails
        ]

    async def get_pending_suggestions(self, user_id: str, limit: int = 20) -> List[Suggestion]:
        result = await self.db.execute(
            select(Suggestion)
            .where(Suggestion.user_id == user_id)
            .where(Suggestion.status == "pending")
            .order_by(desc(Suggestion.created_at))
            .limit(limit)
        )

        return result.scalars().all()
