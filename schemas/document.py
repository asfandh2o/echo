from pydantic import BaseModel
from typing import Optional, Dict, Any
from datetime import datetime


class DocumentResponse(BaseModel):
    id: str
    name: str
    mime_type: str
    drive_link: Optional[str] = None
    owner_email: Optional[str] = None
    status: str
    chunk_count: int
    file_size: Optional[int] = None
    drive_created_at: Optional[datetime] = None
    drive_modified_at: Optional[datetime] = None
    last_indexed_at: Optional[datetime] = None

    model_config = {"from_attributes": True}


class DocumentSearchResult(BaseModel):
    content: str
    document_name: str
    drive_link: Optional[str] = None
    modified_at: str
    mime_type: str
    relevance_rank: float


class DocumentStats(BaseModel):
    total_documents: int
    indexed_documents: int
    total_chunks: int
    last_scan_at: Optional[datetime] = None
    documents_by_type: Dict[str, int]
