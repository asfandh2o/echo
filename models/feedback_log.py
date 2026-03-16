from sqlalchemy import Column, DateTime, ForeignKey, Float, Text
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship
from db.session import Base
import uuid


class FeedbackLog(Base):
    __tablename__ = "feedback_logs"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, index=True)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    suggestion_id = Column(UUID(as_uuid=True), ForeignKey("suggestions.id", ondelete="CASCADE"), nullable=False, index=True)
    feedback_type = Column(Text, nullable=False)
    diff_score = Column(Float)
    original_text = Column(Text, nullable=False)
    final_text = Column(Text, nullable=False)
    extra_data = Column("metadata", JSONB, default=dict)
    timestamp = Column(DateTime(timezone=True), server_default=func.now(), nullable=False, index=True)

    suggestion = relationship("Suggestion", back_populates="feedback_logs")
