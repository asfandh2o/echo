from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, desc, func
from db.session import get_db
from models.user import User
from models.drive_document import DriveDocument
from models.document_chunk import DocumentChunk
from api.deps import get_current_user
from services.document_service import DocumentService
from schemas.document import DocumentResponse, DocumentSearchResult, DocumentStats
from workers.celery_app import celery_app
from core.logging import get_logger
from typing import List

router = APIRouter(prefix="/documents", tags=["documents"])
logger = get_logger(__name__)


@router.get("/", response_model=List[DocumentResponse])
async def list_documents(
    status: str = Query(None, description="Filter by status: indexed, pending, failed"),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """List all indexed documents for the current user."""
    user_id = str(current_user.id)

    query = select(DriveDocument).where(DriveDocument.user_id == user_id)
    if status:
        query = query.where(DriveDocument.status == status)
    query = query.order_by(desc(DriveDocument.drive_modified_at)).offset(offset).limit(limit)

    result = await db.execute(query)
    docs = result.scalars().all()

    return [
        DocumentResponse(
            id=str(doc.id),
            name=doc.name,
            mime_type=doc.mime_type,
            drive_link=doc.drive_link,
            owner_email=doc.owner_email,
            status=doc.status,
            chunk_count=doc.chunk_count,
            file_size=doc.file_size,
            drive_created_at=doc.drive_created_at,
            drive_modified_at=doc.drive_modified_at,
            last_indexed_at=doc.last_indexed_at,
        )
        for doc in docs
    ]


@router.get("/search", response_model=List[DocumentSearchResult])
async def search_documents(
    q: str = Query(..., min_length=1, description="Search query"),
    limit: int = Query(5, ge=1, le=20),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Full-text search across the current user's indexed documents."""
    doc_service = DocumentService()
    results = await doc_service.search_documents(
        db=db,
        user_id=str(current_user.id),
        query=q,
        limit=limit,
    )

    return [DocumentSearchResult(**r) for r in results]


@router.post("/rescan")
async def rescan_drive(
    current_user: User = Depends(get_current_user),
):
    """Trigger a manual Google Drive rescan for the current user."""
    celery_app.send_task(
        "workers.tasks.scan_drive_for_user",
        args=[str(current_user.id)],
    )
    logger.info("drive_rescan_triggered", user_id=str(current_user.id))
    return {"status": "scan_started", "message": "Drive scan has been queued. Documents will be indexed shortly."}


@router.get("/stats", response_model=DocumentStats)
async def document_stats(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Get document indexing statistics for the current user."""
    user_id = str(current_user.id)

    # Total documents
    total_result = await db.execute(
        select(func.count()).select_from(DriveDocument).where(
            DriveDocument.user_id == user_id,
            DriveDocument.status != "deleted",
        )
    )
    total_documents = total_result.scalar() or 0

    # Indexed documents
    indexed_result = await db.execute(
        select(func.count()).select_from(DriveDocument).where(
            DriveDocument.user_id == user_id,
            DriveDocument.status == "indexed",
        )
    )
    indexed_documents = indexed_result.scalar() or 0

    # Total chunks
    chunks_result = await db.execute(
        select(func.count()).select_from(DocumentChunk).where(
            DocumentChunk.user_id == user_id,
        )
    )
    total_chunks = chunks_result.scalar() or 0

    # Last scan time
    last_scan_result = await db.execute(
        select(DriveDocument.last_indexed_at)
        .where(DriveDocument.user_id == user_id)
        .where(DriveDocument.last_indexed_at.isnot(None))
        .order_by(desc(DriveDocument.last_indexed_at))
        .limit(1)
    )
    last_scan_at = last_scan_result.scalar_one_or_none()

    # Documents by type
    type_result = await db.execute(
        select(DriveDocument.mime_type, func.count())
        .where(DriveDocument.user_id == user_id, DriveDocument.status != "deleted")
        .group_by(DriveDocument.mime_type)
    )
    documents_by_type = {row[0]: row[1] for row in type_result.fetchall()}

    return DocumentStats(
        total_documents=total_documents,
        indexed_documents=indexed_documents,
        total_chunks=total_chunks,
        last_scan_at=last_scan_at,
        documents_by_type=documents_by_type,
    )
