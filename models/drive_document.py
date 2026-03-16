from sqlalchemy import Column, String, Integer, DateTime, ForeignKey, Index, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship
from db.session import Base
import uuid


class DriveDocument(Base):
    __tablename__ = "drive_documents"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, index=True)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    drive_file_id = Column(String(255), nullable=False)
    name = Column(String(500), nullable=False)
    mime_type = Column(String(255), nullable=False)
    drive_link = Column(String(1000), nullable=True)
    owner_email = Column(String(255), nullable=True)
    file_size = Column(Integer, nullable=True)
    drive_created_at = Column(DateTime(timezone=True), nullable=True)
    drive_modified_at = Column(DateTime(timezone=True), nullable=True)
    last_indexed_at = Column(DateTime(timezone=True), nullable=True)
    status = Column(String(50), nullable=False, server_default="pending")
    chunk_count = Column(Integer, nullable=False, server_default="0")
    extra_data = Column(JSONB, server_default="{}")
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)

    chunks = relationship("DocumentChunk", back_populates="document", cascade="all, delete-orphan")

    __table_args__ = (
        UniqueConstraint("user_id", "drive_file_id", name="uq_user_drive_file"),
        Index("idx_drive_doc_user_status", "user_id", "status"),
    )
