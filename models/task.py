import uuid
from sqlalchemy import Column, String, DateTime, ForeignKey, Text, Index
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship
from db.session import Base


class Task(Base):
    __tablename__ = "tasks"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, index=True)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    email_id = Column(UUID(as_uuid=True), ForeignKey("emails.id", ondelete="SET NULL"), nullable=True, index=True)

    title = Column(String(500), nullable=False)
    description = Column(Text, nullable=True)
    source = Column(String(50), nullable=False, default="echo")  # echo, hera, manual
    status = Column(String(50), nullable=False, default="pending")  # pending, in_progress, completed, dismissed
    priority = Column(String(20), nullable=False, default="normal")  # low, normal, high, urgent

    extra_data = Column("metadata", JSONB, default=dict)

    due_date = Column(DateTime(timezone=True), nullable=True)
    completed_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)

    user = relationship("User")
    email = relationship("Email")

    __table_args__ = (
        Index("idx_task_user_status", "user_id", "status"),
        Index("idx_task_user_created", "user_id", "created_at"),
        Index("idx_task_source", "user_id", "source"),
    )
