from typing import List, Dict, Any, Optional
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, delete, text, func
from models.drive_document import DriveDocument
from models.document_chunk import DocumentChunk
from services.drive_service import DriveService
from core.logging import get_logger
from core.config import settings
from datetime import datetime
from io import BytesIO
import re

logger = get_logger(__name__)


class DocumentService:

    async def index_document(
        self,
        db: AsyncSession,
        user_id: str,
        drive_file_id: str,
        drive_service: DriveService,
    ) -> DriveDocument:
        """Index a single Drive document: extract text, chunk it, store in DB."""

        # Get the document record
        result = await db.execute(
            select(DriveDocument).where(
                DriveDocument.user_id == user_id,
                DriveDocument.drive_file_id == drive_file_id,
            )
        )
        doc = result.scalar_one_or_none()
        if not doc:
            raise ValueError(f"DriveDocument not found: {drive_file_id}")

        try:
            # Extract text based on file type
            text_content = await self._extract_text(drive_service, doc.drive_file_id, doc.mime_type)

            if not text_content or not text_content.strip():
                doc.status = "failed"
                doc.extra_data = {**(doc.extra_data or {}), "error": "No text content extracted"}
                await db.commit()
                logger.warning("document_empty", drive_file_id=drive_file_id, name=doc.name)
                return doc

            # Chunk the text
            chunks = self._chunk_text(
                text_content,
                max_tokens=settings.DRIVE_CHUNK_SIZE_TOKENS,
                overlap_tokens=settings.DRIVE_CHUNK_OVERLAP_TOKENS,
            )

            # Delete old chunks for this document (re-indexing)
            await db.execute(
                delete(DocumentChunk).where(DocumentChunk.document_id == doc.id)
            )

            # Create new chunks
            for i, chunk_text in enumerate(chunks):
                chunk = DocumentChunk(
                    document_id=doc.id,
                    user_id=user_id,
                    chunk_index=i,
                    content=chunk_text,
                    token_count=self._estimate_tokens(chunk_text),
                    extra_data={"document_name": doc.name, "mime_type": doc.mime_type},
                )
                db.add(chunk)

            # Update document status
            doc.status = "indexed"
            doc.chunk_count = len(chunks)
            doc.last_indexed_at = datetime.utcnow()

            await db.commit()
            await db.refresh(doc)

            logger.info(
                "document_indexed",
                drive_file_id=drive_file_id,
                name=doc.name,
                chunks=len(chunks),
                total_tokens=sum(self._estimate_tokens(c) for c in chunks),
            )
            return doc

        except Exception as e:
            doc.status = "failed"
            doc.extra_data = {**(doc.extra_data or {}), "error": str(e)[:500]}
            await db.commit()
            logger.error("document_index_failed", drive_file_id=drive_file_id, error=str(e))
            raise

    async def list_user_documents(
        self,
        db: AsyncSession,
        user_id: str,
    ) -> List[Dict[str, str]]:
        """Return a lightweight list of all indexed documents for a user."""
        result = await db.execute(
            select(DriveDocument).where(
                DriveDocument.user_id == user_id,
                DriveDocument.status == "indexed",
            ).order_by(DriveDocument.drive_modified_at.desc())
        )
        docs = result.scalars().all()
        return [
            {
                "name": doc.name,
                "mime_type": doc.mime_type,
                "modified_at": doc.drive_modified_at.isoformat() if doc.drive_modified_at else "unknown",
            }
            for doc in docs
        ]

    async def search_documents(
        self,
        db: AsyncSession,
        user_id: str,
        query: str,
        limit: int = 5,
    ) -> List[Dict[str, Any]]:
        """Full-text search across a user's indexed documents.

        Returns top matching chunks with document metadata.
        All results are filtered by user_id for access control.
        """
        if not query or not query.strip():
            return []

        # Clean query for tsquery — remove special chars that break plainto_tsquery
        clean_query = re.sub(r'[^\w\s]', ' ', query).strip()
        if not clean_query:
            return []

        # Extract meaningful words for document name matching (drop common stop words)
        stop_words = {"what", "is", "in", "my", "the", "a", "an", "of", "to", "and", "or", "for",
                       "about", "tell", "me", "show", "get", "can", "you", "do", "does", "how",
                       "from", "this", "that", "with", "it", "its", "has", "have", "been", "are",
                       "was", "were", "be", "will", "would", "could", "should", "all", "any",
                       "document", "file", "spreadsheet", "sheet", "doc", "pdf", "drive",
                       "list", "give", "find", "search", "look", "need", "want", "know"}
        name_words = [w for w in clean_query.lower().split() if w not in stop_words and len(w) > 2]

        # Basic stemming: strip common suffixes for better name matching
        stemmed_words = set()
        for w in name_words:
            stemmed_words.add(w)
            if w.endswith("es") and len(w) > 4:
                stemmed_words.add(w[:-2])
            elif w.endswith("s") and len(w) > 3:
                stemmed_words.add(w[:-1])
            if w.endswith("ing") and len(w) > 5:
                stemmed_words.add(w[:-3])
            if w.endswith("ed") and len(w) > 4:
                stemmed_words.add(w[:-2])

        # Build name matching: OR-based — any stemmed word matching the doc name counts
        stemmed_list = list(stemmed_words)[:12]
        name_conditions = []
        name_params = {}
        for i, word in enumerate(stemmed_list):
            param_key = f"nw{i}"
            name_conditions.append(f"dd.name ILIKE :{param_key}")
            name_params[param_key] = f"%{word}%"

        name_clause = " OR ".join(name_conditions) if name_conditions else "FALSE"

        sql = text(f"""
            SELECT dc.content, dd.name AS document_name, dd.drive_link,
                   dd.drive_modified_at AS modified_at, dd.mime_type,
                   ts_rank(dc.search_vector, plainto_tsquery('english', :query)) AS rank
            FROM document_chunks dc
            JOIN drive_documents dd ON dd.id = dc.document_id
            WHERE dc.user_id = cast(:user_id as uuid)
              AND dd.status = 'indexed'
              AND (
                  dc.search_vector @@ plainto_tsquery('english', :query)
                  OR ({name_clause})
              )
            ORDER BY rank DESC
            LIMIT :limit
        """)

        result = await db.execute(
            sql,
            {"user_id": str(user_id), "query": clean_query, "limit": limit, **name_params},
        )
        rows = result.fetchall()

        results = []
        for row in rows:
            results.append({
                "content": row.content,
                "document_name": row.document_name,
                "link": row.drive_link,
                "modified_at": row.modified_at.isoformat() if row.modified_at else "unknown",
                "mime_type": row.mime_type,
                "relevance_rank": float(row.rank),
            })

        logger.info("document_search", user_id=user_id, query_length=len(query), results=len(results))
        return results

    async def _extract_text(self, drive_service: DriveService, file_id: str, mime_type: str) -> str:
        """Extract text from a Drive file based on its type."""
        if DriveService.is_google_native(mime_type):
            return await drive_service.export_google_doc(file_id, mime_type)

        # Download and extract
        file_bytes = await drive_service.download_file(file_id)

        if mime_type == "application/pdf":
            return self._extract_pdf_text(file_bytes)
        elif mime_type == "application/vnd.openxmlformats-officedocument.wordprocessingml.document":
            return self._extract_docx_text(file_bytes)
        elif mime_type.startswith("text/"):
            return file_bytes.decode("utf-8", errors="ignore")
        else:
            logger.warning("unsupported_mime_type", mime_type=mime_type)
            return ""

    def _extract_pdf_text(self, file_bytes: bytes) -> str:
        """Extract text from PDF bytes using PyPDF2."""
        try:
            from PyPDF2 import PdfReader
            reader = PdfReader(BytesIO(file_bytes))
            pages = []
            for page in reader.pages:
                page_text = page.extract_text()
                if page_text:
                    pages.append(page_text)
            return "\n\n".join(pages)
        except Exception as e:
            logger.error("pdf_extraction_failed", error=str(e))
            return ""

    def _extract_docx_text(self, file_bytes: bytes) -> str:
        """Extract text from DOCX bytes using python-docx."""
        try:
            from docx import Document
            doc = Document(BytesIO(file_bytes))
            paragraphs = []
            for para in doc.paragraphs:
                if para.text.strip():
                    paragraphs.append(para.text)
            return "\n\n".join(paragraphs)
        except Exception as e:
            logger.error("docx_extraction_failed", error=str(e))
            return ""

    def _chunk_text(
        self,
        text_content: str,
        max_tokens: int = 800,
        overlap_tokens: int = 100,
    ) -> List[str]:
        """Split text into chunks of ~max_tokens with overlap.

        Strategy:
        1. Split on double newlines (paragraphs)
        2. If a paragraph exceeds max_tokens, split on sentences
        3. Join paragraphs into chunks up to max_tokens
        4. Add overlap from previous chunk
        """
        if not text_content.strip():
            return []

        # Split into paragraphs
        paragraphs = re.split(r'\n\s*\n', text_content)
        paragraphs = [p.strip() for p in paragraphs if p.strip()]

        # Split long paragraphs into sentences
        segments = []
        for para in paragraphs:
            if self._estimate_tokens(para) > max_tokens:
                # Split on sentence boundaries
                sentences = re.split(r'(?<=[.!?])\s+', para)
                segments.extend(s for s in sentences if s.strip())
            else:
                segments.append(para)

        # Build chunks
        chunks = []
        current_chunk = []
        current_tokens = 0

        for segment in segments:
            seg_tokens = self._estimate_tokens(segment)

            if current_tokens + seg_tokens > max_tokens and current_chunk:
                # Save current chunk
                chunk_text = "\n\n".join(current_chunk)
                chunks.append(chunk_text)

                # Start new chunk with overlap
                overlap_text = self._get_overlap(current_chunk, overlap_tokens)
                if overlap_text:
                    current_chunk = [overlap_text, segment]
                    current_tokens = self._estimate_tokens(overlap_text) + seg_tokens
                else:
                    current_chunk = [segment]
                    current_tokens = seg_tokens
            else:
                current_chunk.append(segment)
                current_tokens += seg_tokens

        # Don't forget the last chunk
        if current_chunk:
            chunks.append("\n\n".join(current_chunk))

        return chunks

    def _get_overlap(self, segments: List[str], overlap_tokens: int) -> str:
        """Get the last ~overlap_tokens from the segments for chunk overlap."""
        combined = "\n\n".join(segments)
        words = combined.split()
        # Approximate: overlap_tokens / 1.3 ≈ number of words
        overlap_words = int(overlap_tokens / 1.3)
        if len(words) <= overlap_words:
            return combined
        return " ".join(words[-overlap_words:])

    @staticmethod
    def _estimate_tokens(text_content: str) -> int:
        """Rough token estimate: ~1.3 tokens per word."""
        return int(len(text_content.split()) * 1.3)
