from sqlalchemy import Column, String, DateTime, Text, ForeignKey, Index, Date
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.sql import func
from db.session import Base
import uuid


class Digest(Base):
    __tablename__ = "digests"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, index=True)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    digest_date = Column(Date, nullable=False)
    content = Column(JSONB, nullable=False)
    llm_summary = Column(Text)
    status = Column(String(50), default="completed", nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    __table_args__ = (
        Index("idx_digest_user_date", "user_id", "digest_date", unique=True),
    )
