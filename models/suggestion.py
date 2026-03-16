from sqlalchemy import Column, String, DateTime, ForeignKey, Float, Text, Index
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship
from db.session import Base
import uuid


class Suggestion(Base):
    __tablename__ = "suggestions"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, index=True)
    email_id = Column(UUID(as_uuid=True), ForeignKey("emails.id", ondelete="CASCADE"), nullable=False, index=True)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    suggestion_text = Column(Text, nullable=False)
    final_text = Column(Text)
    feedback_type = Column(String(50))
    confidence_score = Column(Float, nullable=False)
    status = Column(String(50), default="pending", nullable=False)
    reasoning = Column(Text)
    context_used = Column(JSONB, default=dict)
    extra_data = Column("metadata", JSONB, default=dict)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)

    email = relationship("Email", back_populates="suggestions")
    feedback_logs = relationship("FeedbackLog", back_populates="suggestion", cascade="all, delete-orphan")

    __table_args__ = (
        Index("idx_user_status", "user_id", "status"),
        Index("idx_email_created", "email_id", "created_at"),
    )
