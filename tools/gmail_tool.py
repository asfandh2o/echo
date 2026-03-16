from typing import List, Dict, Any, Optional
from services.gmail_service import GmailService
from core.logging import get_logger

logger = get_logger(__name__)


class GmailTool:
    def __init__(self, gmail_service: GmailService, user_id: str):
        self.gmail_service = gmail_service
        self.user_id = user_id

    async def send_email_safe(
        self,
        to: List[str],
        subject: str,
        body: str,
        thread_id: Optional[str] = None,
        require_confirmation: bool = True,
        auto_approved: bool = False
    ) -> Dict[str, Any]:
        if require_confirmation and not auto_approved:
            logger.warning(
                "send_blocked_requires_confirmation",
                user_id=self.user_id,
                recipients=to
            )
            return {
                "status": "blocked",
                "reason": "Manual confirmation required",
                "preview": {
                    "to": to,
                    "subject": subject,
                    "body": body[:200]
                }
            }

        message_id = await self.gmail_service.send_email(
            to=to,
            subject=subject,
            body=body,
            thread_id=thread_id
        )

        logger.info(
            "email_sent_via_tool",
            user_id=self.user_id,
            message_id=message_id,
            recipients=to,
            auto_approved=auto_approved
        )

        return {
            "status": "sent",
            "message_id": message_id,
            "recipients": to
        }

    async def fetch_emails(self, max_results: int = 50, query: str = "") -> List[Dict[str, Any]]:
        logger.info("fetching_emails_via_tool", user_id=self.user_id, max_results=max_results)

        emails = await self.gmail_service.fetch_recent_emails(
            max_results=max_results,
            query=query
        )

        return emails

    async def get_thread(self, thread_id: str) -> List[Dict[str, Any]]:
        logger.info("fetching_thread_via_tool", user_id=self.user_id, thread_id=thread_id)

        messages = await self.gmail_service.get_thread_messages(thread_id)

        return messages
