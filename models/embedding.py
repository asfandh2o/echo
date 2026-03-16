from sqlalchemy import Column, String, DateTime, ForeignKey, Index, Text
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship
from db.session import Base
from pgvector.sqlalchemy import Vector
import uuid


class Embedding(Base):
    __tablename__ = "embeddings"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, index=True)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    email_id = Column(UUID(as_uuid=True), ForeignKey("emails.id", ondelete="CASCADE"), nullable=False, index=True)
    vector = Column(Vector(1536), nullable=False)
    embedding_model = Column(String(100), default="text-embedding-3-small", nullable=False)
    text_content = Column(Text, nullable=False)
    extra_data = Column("metadata", JSONB, default=dict)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    email = relationship("Email", back_populates="embeddings")

    __table_args__ = (
        Index("idx_user_embedding", "user_id"),
    )
