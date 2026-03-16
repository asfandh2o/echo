from sqlalchemy import Column, String, Integer, Text, DateTime, ForeignKey, Index
from sqlalchemy.dialects.postgresql import UUID, JSONB, TSVECTOR
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship
from db.session import Base
import uuid


class DocumentChunk(Base):
    __tablename__ = "document_chunks"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, index=True)
    document_id = Column(UUID(as_uuid=True), ForeignKey("drive_documents.id", ondelete="CASCADE"), nullable=False, index=True)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    chunk_index = Column(Integer, nullable=False, server_default="0")
    content = Column(Text, nullable=False)
    search_vector = Column(TSVECTOR)
    token_count = Column(Integer, nullable=False, server_default="0")
    extra_data = Column(JSONB, server_default="{}")
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    document = relationship("DriveDocument", back_populates="chunks")

    __table_args__ = (
        Index("idx_chunk_search_vector", "search_vector", postgresql_using="gin"),
        Index("idx_chunk_user_document", "user_id", "document_id"),
    )
