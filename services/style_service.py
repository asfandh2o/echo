from typing import Dict, Any, List
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, desc
from models.style_profile import StyleProfile
from models.email import Email
from models.feedback_log import FeedbackLog
from core.config import settings
from core.logging import get_logger
import re
import difflib
from datetime import datetime
from collections import Counter

logger = get_logger(__name__)


class StyleService:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def build_style_profile(self, user_id: str) -> StyleProfile:
        result = await self.db.execute(
            select(Email)
            .where(Email.user_id == user_id)
            .where(Email.sender.contains(user_id))
            .order_by(desc(Email.received_at))
            .limit(settings.STYLE_PROFILE_SAMPLE_SIZE)
        )
        sent_emails = result.scalars().all()

        if not sent_emails:
            logger.warning("no_sent_emails_found", user_id=user_id)
            return await self._create_default_profile(user_id)

        profile_data = self._analyze_emails(sent_emails)

        existing = await self.db.execute(
            select(StyleProfile).where(StyleProfile.user_id == user_id)
        )
        profile = existing.scalar_one_or_none()

        if profile:
            profile.profile_json = profile_data
            profile.sample_size = len(sent_emails)
            profile.version += 1
        else:
            profile = StyleProfile(
                user_id=user_id,
                profile_json=profile_data,
                sample_size=len(sent_emails),
                version=1
            )
            self.db.add(profile)

        await self.db.commit()
        await self.db.refresh(profile)

        logger.info("style_profile_built", user_id=user_id, sample_size=len(sent_emails))

        return profile

    def _analyze_emails(self, emails: List[Email]) -> Dict[str, Any]:
        bodies = [email.body for email in emails]

        word_counts = [len(body.split()) for body in bodies]
        avg_length = sum(word_counts) // len(word_counts) if word_counts else 0

        greetings = self._extract_greetings(bodies)
        signoffs = self._extract_signoffs(bodies)

        emoji_count = sum(self._count_emojis(body) for body in bodies)
        emoji_usage = emoji_count / len(bodies) if bodies else 0

        tone = self._detect_tone(bodies)
        formality = self._detect_formality(bodies)

        common_phrases = self._extract_common_phrases(bodies)

        return {
            "tone": tone,
            "formality": formality,
            "avg_length": avg_length,
            "greeting_patterns": greetings,
            "signoff_patterns": signoffs,
            "emoji_usage": emoji_usage,
            "common_phrases": common_phrases,
            "response_speed": "medium"
        }

    def _extract_greetings(self, bodies: List[str]) -> List[str]:
        greeting_patterns = [
            r"^(Hi|Hello|Hey|Dear|Good morning|Good afternoon)\s+[\w\s,]+",
        ]

        greetings = []
        for body in bodies:
            first_line = body.split("\n")[0].strip()
            for pattern in greeting_patterns:
                if match := re.search(pattern, first_line, re.IGNORECASE):
                    greetings.append(match.group(0))

        counter = Counter(greetings)
        return [g for g, _ in counter.most_common(5)]

    def _extract_signoffs(self, bodies: List[str]) -> List[str]:
        signoff_patterns = [
            r"(Best regards|Best|Thanks|Thank you|Regards|Sincerely|Cheers)[\s,]*$",
        ]

        signoffs = []
        for body in bodies:
            lines = body.strip().split("\n")
            last_lines = "\n".join(lines[-3:]) if len(lines) >= 3 else body

            for pattern in signoff_patterns:
                if match := re.search(pattern, last_lines, re.IGNORECASE | re.MULTILINE):
                    signoffs.append(match.group(1))

        counter = Counter(signoffs)
        return [s for s, _ in counter.most_common(5)]

    def _count_emojis(self, text: str) -> int:
        emoji_pattern = re.compile(
            "["
            u"\U0001F600-\U0001F64F"
            u"\U0001F300-\U0001F5FF"
            u"\U0001F680-\U0001F6FF"
            u"\U0001F1E0-\U0001F1FF"
            "]+",
            flags=re.UNICODE
        )
        return len(emoji_pattern.findall(text))

    def _detect_tone(self, bodies: List[str]) -> str:
        combined = " ".join(bodies).lower()

        exclamation_count = combined.count("!")
        question_count = combined.count("?")
        word_count = len(combined.split())

        if word_count == 0:
            return "neutral"

        exclamation_ratio = exclamation_count / word_count

        if exclamation_ratio > 0.02:
            return "enthusiastic"
        elif question_count > exclamation_count:
            return "inquisitive"
        else:
            return "neutral"

    def _detect_formality(self, bodies: List[str]) -> str:
        combined = " ".join(bodies).lower()

        formal_indicators = ["dear", "sincerely", "regards", "cordially", "respectfully"]
        casual_indicators = ["hey", "hi there", "cheers", "thanks!", "cool", "awesome"]

        formal_count = sum(combined.count(word) for word in formal_indicators)
        casual_count = sum(combined.count(word) for word in casual_indicators)

        if formal_count > casual_count * 1.5:
            return "formal"
        elif casual_count > formal_count * 1.5:
            return "casual"
        else:
            return "neutral"

    def _extract_common_phrases(self, bodies: List[str]) -> List[str]:
        combined = " ".join(bodies).lower()

        phrases = re.findall(r'\b\w+\s+\w+\s+\w+\b', combined)

        counter = Counter(phrases)
        return [phrase for phrase, count in counter.most_common(10) if count > 2]

    async def _create_default_profile(self, user_id: str) -> StyleProfile:
        # Check if one was created by a concurrent task
        existing = await self.db.execute(
            select(StyleProfile).where(StyleProfile.user_id == user_id)
        )
        profile = existing.scalar_one_or_none()
        if profile:
            return profile

        profile = StyleProfile(
            user_id=user_id,
            profile_json={
                "tone": "neutral",
                "formality": "neutral",
                "avg_length": 100,
                "greeting_patterns": ["Hi"],
                "signoff_patterns": ["Best regards"],
                "emoji_usage": 0.0,
                "common_phrases": [],
                "response_speed": "medium"
            },
            sample_size=0,
            version=1
        )

        try:
            self.db.add(profile)
            await self.db.commit()
            await self.db.refresh(profile)
        except Exception:
            await self.db.rollback()
            result = await self.db.execute(
                select(StyleProfile).where(StyleProfile.user_id == user_id)
            )
            profile = result.scalar_one_or_none()

        return profile

    async def apply_feedback_learning(self, user_id: str) -> StyleProfile:
        """Analyze recent feedback to refine the style profile."""
        result = await self.db.execute(
            select(FeedbackLog)
            .where(FeedbackLog.user_id == user_id)
            .where(FeedbackLog.feedback_type.in_(["edited", "rejected"]))
            .where(FeedbackLog.diff_score < 0.95)
            .order_by(desc(FeedbackLog.timestamp))
            .limit(20)
        )
        feedback_logs = result.scalars().all()

        if not feedback_logs:
            return await self._get_or_create_profile(user_id)

        adjustments = self._analyze_feedback(feedback_logs)

        profile = await self._get_or_create_profile(user_id)
        profile_data = dict(profile.profile_json)
        profile_data["feedback_adjustments"] = adjustments
        profile.profile_json = profile_data
        profile.version += 1

        await self.db.commit()
        await self.db.refresh(profile)

        logger.info("feedback_learning_applied", user_id=user_id, feedback_count=len(feedback_logs))
        return profile

    async def _get_or_create_profile(self, user_id: str) -> StyleProfile:
        result = await self.db.execute(
            select(StyleProfile).where(StyleProfile.user_id == user_id)
        )
        profile = result.scalar_one_or_none()
        if not profile:
            profile = await self._create_default_profile(user_id)
        return profile

    def _analyze_feedback(self, feedback_logs: List) -> Dict[str, Any]:
        final_texts = [fl.final_text for fl in feedback_logs if fl.final_text]

        if not final_texts:
            return {}

        tone = self._detect_tone(final_texts)
        formality = self._detect_formality(final_texts)
        greetings = self._extract_greetings(final_texts)
        signoffs = self._extract_signoffs(final_texts)

        word_counts = [len(t.split()) for t in final_texts]
        avg_length = sum(word_counts) // len(word_counts) if word_counts else 100

        corrections = []
        for fl in feedback_logs[:10]:
            if fl.original_text and fl.final_text and fl.diff_score and fl.diff_score < 0.90:
                diff_pairs = self._extract_diff_pairs(fl.original_text, fl.final_text)
                corrections.extend(diff_pairs)

        diff_scores = [fl.diff_score for fl in feedback_logs if fl.diff_score is not None]
        avg_diff = sum(diff_scores) / len(diff_scores) if diff_scores else 0.5

        return {
            "preferred_tone": tone,
            "preferred_formality": formality,
            "avg_edited_length": avg_length,
            "preferred_greetings": greetings[:3],
            "preferred_signoffs": signoffs[:3],
            "correction_patterns": corrections[:10],
            "feedback_count": len(feedback_logs),
            "avg_diff_score": round(avg_diff, 3),
            "last_updated": datetime.utcnow().isoformat()
        }

    def _extract_diff_pairs(self, original: str, final: str) -> List[Dict[str, str]]:
        """Extract replaced phrases from original->final text diffs."""
        pairs = []
        matcher = difflib.SequenceMatcher(None, original.split(), final.split())
        for tag, i1, i2, j1, j2 in matcher.get_opcodes():
            if tag == "replace":
                orig_phrase = " ".join(original.split()[i1:i2])
                new_phrase = " ".join(final.split()[j1:j2])
                if len(orig_phrase) > 3 and len(new_phrase) > 3:
                    pairs.append({"original_phrase": orig_phrase, "corrected_to": new_phrase})
        return pairs

    async def get_style_profile(self, user_id: str) -> Dict[str, Any]:
        result = await self.db.execute(
            select(StyleProfile).where(StyleProfile.user_id == user_id)
        )
        profile = result.scalar_one_or_none()

        if not profile:
            profile = await self._create_default_profile(user_id)

        return profile.profile_json if profile else {
            "tone": "neutral",
            "formality": "neutral",
            "avg_length": 100
        }
