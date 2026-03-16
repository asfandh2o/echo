from typing import List, Dict, Any, Optional
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from core.security import token_encryption
from core.logging import get_logger
import json
import base64
from datetime import datetime
from email.utils import parsedate_to_datetime

logger = get_logger(__name__)


class GmailService:
    def __init__(self, encrypted_tokens: str):
        self.encrypted_tokens = encrypted_tokens
        self.service = None

    async def _get_service(self):
        if self.service:
            return self.service

        decrypted = token_encryption.decrypt(self.encrypted_tokens)
        token_data = json.loads(decrypted)

        credentials = Credentials(
            token=token_data.get("access_token"),
            refresh_token=token_data.get("refresh_token"),
            token_uri="https://oauth2.googleapis.com/token",
            client_id=token_data.get("client_id"),
            client_secret=token_data.get("client_secret"),
        )

        self.service = build("gmail", "v1", credentials=credentials)
        return self.service

    async def fetch_recent_emails(self, max_results: int = 50, query: str = "") -> List[Dict[str, Any]]:
        try:
            service = await self._get_service()

            results = service.users().messages().list(
                userId="me",
                maxResults=max_results,
                q=query
            ).execute()

            messages = results.get("messages", [])

            emails = []
            for msg in messages:
                email_data = await self._fetch_message_detail(msg["id"])
                if email_data:
                    emails.append(email_data)

            logger.info("emails_fetched", count=len(emails))
            return emails

        except HttpError as error:
            logger.error("gmail_fetch_error", error=str(error))
            raise

    async def _fetch_message_detail(self, message_id: str) -> Optional[Dict[str, Any]]:
        try:
            service = await self._get_service()

            message = service.users().messages().get(
                userId="me",
                id=message_id,
                format="full"
            ).execute()

            headers = {h["name"]: h["value"] for h in message["payload"]["headers"]}

            body = self._get_message_body(message["payload"])

            date_str = headers.get("Date", "")
            try:
                received_at = parsedate_to_datetime(date_str)
            except:
                received_at = datetime.utcnow()

            return {
                "gmail_message_id": message_id,
                "thread_id": message.get("threadId", ""),
                "subject": headers.get("Subject", ""),
                "sender": headers.get("From", ""),
                "recipients": self._parse_recipients(headers.get("To", "")),
                "cc": self._parse_recipients(headers.get("Cc", "")),
                "bcc": self._parse_recipients(headers.get("Bcc", "")),
                "body": body.get("text", ""),
                "html_body": body.get("html"),
                "received_at": received_at,
            }

        except HttpError as error:
            logger.error("message_detail_error", message_id=message_id, error=str(error))
            return None

    def _get_message_body(self, payload: Dict) -> Dict[str, str]:
        result = {"text": "", "html": None}

        if "parts" in payload:
            for part in payload["parts"]:
                if part["mimeType"] == "text/plain":
                    data = part.get("body", {}).get("data", "")
                    result["text"] = base64.urlsafe_b64decode(data).decode("utf-8", errors="ignore")
                elif part["mimeType"] == "text/html":
                    data = part.get("body", {}).get("data", "")
                    result["html"] = base64.urlsafe_b64decode(data).decode("utf-8", errors="ignore")
        else:
            data = payload.get("body", {}).get("data", "")
            if data:
                result["text"] = base64.urlsafe_b64decode(data).decode("utf-8", errors="ignore")

        return result

    def _parse_recipients(self, recipients_str: str) -> List[str]:
        if not recipients_str:
            return []
        return [r.strip() for r in recipients_str.split(",")]

    async def send_email(
        self,
        to: List[str],
        subject: str,
        body: str,
        thread_id: Optional[str] = None,
        cc: Optional[List[str]] = None,
        bcc: Optional[List[str]] = None
    ) -> str:
        try:
            service = await self._get_service()

            message = self._create_message(to, subject, body, cc, bcc)

            if thread_id:
                message["threadId"] = thread_id

            result = service.users().messages().send(userId="me", body=message).execute()

            logger.info("email_sent", message_id=result["id"], recipients=to)
            return result["id"]

        except HttpError as error:
            logger.error("email_send_error", error=str(error))
            raise

    def _create_message(
        self,
        to: List[str],
        subject: str,
        body: str,
        cc: Optional[List[str]] = None,
        bcc: Optional[List[str]] = None
    ) -> Dict[str, str]:
        from email.mime.text import MIMEText

        message = MIMEText(body)
        message["to"] = ", ".join(to)
        message["subject"] = subject

        if cc:
            message["cc"] = ", ".join(cc)
        if bcc:
            message["bcc"] = ", ".join(bcc)

        raw = base64.urlsafe_b64encode(message.as_bytes()).decode()
        return {"raw": raw}

    async def get_thread_messages(self, thread_id: str) -> List[Dict[str, Any]]:
        try:
            service = await self._get_service()

            thread = service.users().threads().get(
                userId="me",
                id=thread_id,
                format="full"
            ).execute()

            messages = []
            for msg in thread.get("messages", []):
                detail = await self._fetch_message_detail(msg["id"])
                if detail:
                    messages.append(detail)

            return messages

        except HttpError as error:
            logger.error("thread_fetch_error", thread_id=thread_id, error=str(error))
            return []
