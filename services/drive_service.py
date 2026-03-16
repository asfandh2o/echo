from typing import List, Dict, Any, Optional
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from googleapiclient.http import MediaIoBaseDownload
from core.security import token_encryption
from core.logging import get_logger
import json
import io

logger = get_logger(__name__)

# Google native types that need export (not download)
GOOGLE_EXPORT_TYPES = {
    "application/vnd.google-apps.document": "text/plain",
    "application/vnd.google-apps.spreadsheet": "text/csv",
    "application/vnd.google-apps.presentation": "text/plain",
}

# File types we can index (download + extract text)
DOWNLOADABLE_TYPES = {
    "application/pdf",
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    "text/plain",
    "text/csv",
    "text/markdown",
    "text/html",
}

# Types to skip entirely
SKIP_PREFIXES = ("image/", "video/", "audio/", "application/zip", "application/x-")


class DriveService:
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

        self.service = build("drive", "v3", credentials=credentials)
        return self.service

    async def list_files(self, modified_after: Optional[str] = None, page_size: int = 100) -> List[Dict[str, Any]]:
        """List files from user's Google Drive.

        Args:
            modified_after: ISO datetime string — only return files modified after this time
            page_size: Number of files per API page
        """
        try:
            service = await self._get_service()

            query_parts = ["trashed = false"]
            if modified_after:
                query_parts.append(f"modifiedTime > '{modified_after}'")
            query = " and ".join(query_parts)

            fields = "nextPageToken, files(id, name, mimeType, modifiedTime, createdTime, webViewLink, owners, size, parents)"

            all_files = []
            page_token = None

            while True:
                results = service.files().list(
                    q=query,
                    fields=fields,
                    pageSize=page_size,
                    pageToken=page_token,
                    orderBy="modifiedTime desc",
                ).execute()

                files = results.get("files", [])
                all_files.extend(files)

                page_token = results.get("nextPageToken")
                if not page_token:
                    break

            logger.info("drive_files_listed", count=len(all_files))
            return all_files

        except HttpError as error:
            logger.error("drive_list_error", error=str(error))
            raise

    async def export_google_doc(self, file_id: str, mime_type: str) -> str:
        """Export a Google native document (Docs, Sheets, Slides) as text.

        Args:
            file_id: Google Drive file ID
            mime_type: The Google mime type of the file
        """
        try:
            service = await self._get_service()
            export_mime = GOOGLE_EXPORT_TYPES.get(mime_type, "text/plain")

            content = service.files().export(
                fileId=file_id,
                mimeType=export_mime,
            ).execute()

            if isinstance(content, bytes):
                return content.decode("utf-8", errors="ignore")
            return str(content)

        except HttpError as error:
            logger.error("drive_export_error", file_id=file_id, error=str(error))
            raise

    async def download_file(self, file_id: str) -> bytes:
        """Download a non-Google file (PDF, DOCX, TXT, etc.) as raw bytes."""
        try:
            service = await self._get_service()

            request = service.files().get_media(fileId=file_id)
            buffer = io.BytesIO()
            downloader = MediaIoBaseDownload(buffer, request)

            done = False
            while not done:
                _, done = downloader.next_chunk()

            buffer.seek(0)
            return buffer.read()

        except HttpError as error:
            logger.error("drive_download_error", file_id=file_id, error=str(error))
            raise

    @staticmethod
    def is_indexable(mime_type: str) -> bool:
        """Check if a file type can be indexed."""
        if mime_type in GOOGLE_EXPORT_TYPES:
            return True
        if mime_type in DOWNLOADABLE_TYPES:
            return True
        if any(mime_type.startswith(prefix) for prefix in SKIP_PREFIXES):
            return False
        return False

    @staticmethod
    def is_google_native(mime_type: str) -> bool:
        """Check if a file is a Google native type (needs export, not download)."""
        return mime_type in GOOGLE_EXPORT_TYPES
