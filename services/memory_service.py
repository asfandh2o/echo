from typing import List, Dict, Any, Optional
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, text
from models.embedding import Embedding
from models.email import Email
from services.llm_router import llm_router
from core.logging import get_logger
import numpy as np

logger = get_logger(__name__)


class MemoryService:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def create_embedding(self, email_id: str, user_id: str) -> Embedding:
        result = await self.db.execute(
            select(Email).where(Email.id == email_id)
        )
        email = result.scalar_one_or_none()

        if not email:
            raise ValueError(f"Email {email_id} not found")

        text_content = f"{email.subject}\n\n{email.body}"

        vector = await llm_router.generate_embedding(text_content)

        embedding = Embedding(
            user_id=user_id,
            email_id=email_id,
            vector=vector,
            text_content=text_content,
            extra_data={"subject": email.subject, "sender": email.sender}
        )

        self.db.add(embedding)
        await self.db.commit()
        await self.db.refresh(embedding)

        logger.info("embedding_created", email_id=email_id)

        return embedding

    async def find_similar_emails(
        self,
        query_text: str,
        user_id: str,
        top_k: int = 5,
        threshold: float = 0.7
    ) -> List[Dict[str, Any]]:
        try:
            query_vector = await llm_router.generate_embedding(query_text)
            query_vector_str = "[" + ",".join(map(str, query_vector)) + "]"

            # Use cast() to avoid asyncpg conflict between :param and ::type
            sql = text(
                "SELECT e.id, e.subject, e.sender, e.body, e.received_at, "
                "emb.vector <=> cast(:query_vector as vector) AS distance "
                "FROM embeddings emb "
                "JOIN emails e ON e.id = emb.email_id "
                "WHERE emb.user_id = cast(:user_id as uuid) "
                "ORDER BY distance "
                "LIMIT :top_k"
            )

            result = await self.db.execute(
                sql,
                {"query_vector": query_vector_str, "user_id": str(user_id), "top_k": top_k}
            )

            rows = result.fetchall()

            similar_emails = []
            for row in rows:
                similarity = 1 - row.distance
                if similarity >= threshold:
                    similar_emails.append({
                        "id": str(row.id),
                        "subject": row.subject,
                        "sender": row.sender,
                        "body": row.body,
                        "received_at": row.received_at,
                        "similarity": similarity
                    })

            logger.info("similar_emails_found", count=len(similar_emails), query_length=len(query_text))
            return similar_emails

        except Exception as e:
            logger.warning("similar_emails_search_failed", error=str(e))
            return []

    async def bulk_create_embeddings(self, user_id: str, limit: int = 50) -> int:
        result = await self.db.execute(
            select(Email.id)
            .where(Email.user_id == user_id)
            .where(~Email.id.in_(
                select(Embedding.email_id).where(Embedding.user_id == user_id)
            ))
            .limit(limit)
        )
        email_ids = [str(row[0]) for row in result.fetchall()]

        created_count = 0
        for email_id in email_ids:
            try:
                await self.create_embedding(email_id, user_id)
                created_count += 1
            except Exception as e:
                logger.error("embedding_creation_failed", email_id=email_id, error=str(e))

        logger.info("bulk_embeddings_created", count=created_count)
        return created_count
