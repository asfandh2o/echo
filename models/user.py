

from sqlalchemy import Column, String, Integer, DateTime, Text
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.sql import func
from db.session import Base
import uuid


class User(Base):
    __tablename__ = "users"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, index=True)
    email = Column(String(255), unique=True, nullable=False, index=True)
    encrypted_oauth_tokens = Column(Text, nullable=False)
    timezone = Column(String(50), default="Asia/Karachi", nullable=False)
    autonomy_level = Column(String(50), default="supervised", nullable=False)
    token_budget = Column(Integer, default=100000, nullable=False)
    tokens_used_today = Column(Integer, default=0, nullable=False)
    extra_data = Column("metadata", JSONB, default=dict)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)
