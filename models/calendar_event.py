from sqlalchemy import Column, String, DateTime, ForeignKey, Text, Index
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship
from db.session import Base
import uuid


class CalendarEvent(Base):
    __tablename__ = "calendar_events"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, index=True)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    email_id = Column(UUID(as_uuid=True), ForeignKey("emails.id", ondelete="SET NULL"), nullable=True, index=True)
    google_event_id = Column(String(255), nullable=False, index=True)
    summary = Column(String(500), nullable=False)
    start_time = Column(DateTime(timezone=True), nullable=False)
    end_time = Column(DateTime(timezone=True), nullable=False)
    attendees = Column(JSONB, default=list)
    location = Column(Text, nullable=True)
    status = Column(String(50), default="created", nullable=False)
    action_type = Column(String(50), nullable=False)
    llm_extraction = Column(JSONB, default=dict)
    extra_data = Column("metadata", JSONB, default=dict)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)

    user = relationship("User")
    email = relationship("Email")

    __table_args__ = (
        Index("idx_calendar_user_status", "user_id", "status"),
        Index("idx_calendar_google_event", "google_event_id"),
    )
