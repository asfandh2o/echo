from sqlalchemy import Column, String, DateTime, Text, ForeignKey, Index
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship
from db.session import Base
import uuid


class Email(Base):
    __tablename__ = "emails"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, index=True)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    gmail_message_id = Column(String(255), nullable=False, index=True)
    thread_id = Column(String(255), nullable=False, index=True)
    subject = Column(Text, nullable=False)
    sender = Column(String(255), nullable=False, index=True)
    recipients = Column(JSONB, nullable=False)
    cc = Column(JSONB, default=list)
    bcc = Column(JSONB, default=list)
    body = Column(Text, nullable=False)
    html_body = Column(Text)
    classification = Column(JSONB)
    extra_data = Column("metadata", JSONB, default=dict)
    received_at = Column(DateTime(timezone=True), nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)

    embeddings = relationship("Embedding", back_populates="email", cascade="all, delete-orphan")
    suggestions = relationship("Suggestion", back_populates="email", cascade="all, delete-orphan")

    __table_args__ = (
        Index("idx_user_received", "user_id", "received_at"),
        Index("idx_user_thread", "user_id", "thread_id"),
    )
