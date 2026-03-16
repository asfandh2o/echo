import re
from typing import Dict, Any, Optional, List
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from models.contact_profile import ContactProfile
from models.email import Email
from core.logging import get_logger

logger = get_logger(__name__)

FREE_DOMAINS = {
    "gmail.com", "yahoo.com", "hotmail.com", "outlook.com",
    "icloud.com", "aol.com", "protonmail.com", "live.com",
}


class ContactService:
    def __init__(self, db: AsyncSession):
        self.db = db

    @staticmethod
    def parse_sender(sender_str: str) -> Dict[str, str]:
        """Parse 'Display Name <email@domain.com>' into components."""
        match = re.match(r'^(.*?)\s*<([^>]+)>', sender_str)
        if match:
            display_name = match.group(1).strip().strip('"')
            email_address = match.group(2).strip().lower()
        else:
            email_address = sender_str.strip().lower()
            display_name = ""

        domain = email_address.split("@")[1] if "@" in email_address else ""
        company = None
        if domain and domain not in FREE_DOMAINS:
            company = domain.split(".")[0].title()

        return {
            "email_address": email_address,
            "display_name": display_name,
            "domain": domain,
            "company": company,
        }

    async def upsert_contact_from_email(self, email: Email, user_id: str) -> ContactProfile:
        """Create or update a contact profile when a new email is processed."""
        parsed = self.parse_sender(email.sender)

        result = await self.db.execute(
            select(ContactProfile)
            .where(ContactProfile.user_id == user_id)
            .where(ContactProfile.email_address == parsed["email_address"])
        )
        contact = result.scalar_one_or_none()

        new_topics = self._extract_topics(email.subject, email.body)

        if contact:
            contact.email_count += 1
            contact.last_contacted = email.received_at
            if parsed["display_name"] and not contact.display_name:
                contact.display_name = parsed["display_name"]
            if parsed["company"] and not contact.company:
                contact.company = parsed["company"]
            existing_topics = contact.topics or []
            merged = list(dict.fromkeys(existing_topics + new_topics))[:20]
            contact.topics = merged
        else:
            contact = ContactProfile(
                user_id=user_id,
                email_address=parsed["email_address"],
                display_name=parsed["display_name"],
                domain=parsed["domain"],
                company=parsed["company"],
                email_count=1,
                first_contacted=email.received_at,
                last_contacted=email.received_at,
                topics=new_topics[:20],
            )
            self.db.add(contact)

        await self.db.commit()
        await self.db.refresh(contact)
        return contact

    async def get_contact_context(self, sender_str: str, user_id: str) -> Optional[Dict[str, Any]]:
        """Get contact profile data formatted for LLM prompt injection."""
        parsed = self.parse_sender(sender_str)

        result = await self.db.execute(
            select(ContactProfile)
            .where(ContactProfile.user_id == user_id)
            .where(ContactProfile.email_address == parsed["email_address"])
        )
        contact = result.scalar_one_or_none()

        if not contact:
            return {
                "name": parsed["display_name"] or parsed["email_address"],
                "email": parsed["email_address"],
                "company": parsed["company"],
                "domain": parsed["domain"],
                "known_contact": False,
            }

        return {
            "name": contact.display_name or parsed["email_address"],
            "email": contact.email_address,
            "company": contact.company,
            "domain": contact.domain,
            "email_count": contact.email_count,
            "first_contacted": contact.first_contacted.isoformat() if contact.first_contacted else None,
            "last_contacted": contact.last_contacted.isoformat() if contact.last_contacted else None,
            "topics": contact.topics or [],
            "relationship_type": contact.relationship_type,
            "interaction_summary": contact.interaction_summary,
            "known_contact": True,
        }

    def _extract_topics(self, subject: str, body: str) -> List[str]:
        """Simple keyword-based topic extraction from subject line."""
        text = (subject or "").lower()
        text = re.sub(r'^(re:|fwd?:|fw:)\s*', '', text, flags=re.IGNORECASE).strip()

        stopwords = {
            "the", "a", "an", "is", "are", "was", "for", "and", "or", "but",
            "in", "on", "at", "to", "of", "with", "from", "by", "up", "about",
            "your", "our", "my", "this", "that", "it", "we", "you", "has", "have",
            "been", "will", "can", "not", "all", "new", "one", "two", "get",
        }
        words = re.findall(r'\b[a-z]{3,}\b', text)
        topics = [w for w in words if w not in stopwords]

        return list(dict.fromkeys(topics))[:5]

    async def build_contact_profiles_from_history(self, user_id: str, limit: int = 200) -> int:
        """Batch-build contact profiles from existing email history."""
        result = await self.db.execute(
            select(Email)
            .where(Email.user_id == user_id)
            .order_by(Email.received_at)
            .limit(limit)
        )
        emails = result.scalars().all()

        count = 0
        for email in emails:
            try:
                await self.upsert_contact_from_email(email, user_id)
                count += 1
            except Exception as e:
                logger.warning("contact_upsert_failed", email_id=str(email.id), error=str(e))

        logger.info("contact_profiles_built", user_id=user_id, count=count)
        return count
