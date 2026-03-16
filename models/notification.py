from sqlalchemy import Column, String, Boolean, DateTime, Text
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.sql import func
from db.session import Base
import uuid


class Notification(Base):
    __tablename__ = "notifications"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, index=True)
    user_id = Column(UUID(as_uuid=True), nullable=False, index=True)
    type = Column(String(50), nullable=False, default="info")  # info, task_assigned, task_updated
    source = Column(String(50), nullable=False, default="echo")  # echo, hera
    title = Column(String(255), nullable=False)
    message = Column(Text, nullable=True)
    read = Column(Boolean, nullable=False, default=False)
    extra_data = Column("meta", JSONB, default=dict)  # extra data (task_id, project_name, etc.)
    action_type = Column(String(50), nullable=True)      # confirm_meeting, etc.
    action_status = Column(String(50), nullable=True)     # pending, confirmed, dismissed
    action_payload = Column(JSONB, nullable=True)         # data needed to execute the action
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
