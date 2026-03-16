from sqlalchemy import Column, String, DateTime, ForeignKey, Integer, Text, Index
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.sql import func
from db.session import Base
import uuid


class ContactProfile(Base):
    __tablename__ = "contact_profiles"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, index=True)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    email_address = Column(String(255), nullable=False)
    display_name = Column(String(255))
    domain = Column(String(255))
    company = Column(String(255))
    email_count = Column(Integer, default=0, nullable=False)
    last_contacted = Column(DateTime(timezone=True))
    first_contacted = Column(DateTime(timezone=True))
    topics = Column(JSONB, default=list)
    relationship_type = Column(String(100))
    interaction_summary = Column(Text)
    extra_data = Column("metadata", JSONB, default=dict)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)

    __table_args__ = (
        Index("idx_contact_user_email", "user_id", "email_address", unique=True),
        Index("idx_contact_user_domain", "user_id", "domain"),
    )
