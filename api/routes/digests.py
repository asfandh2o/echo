from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.ext.asyncio import AsyncSession
from typing import List, Optional
from datetime import date
from db.session import get_db
from models.user import User
from schemas.digest import DigestResponse
from api.deps import get_current_user
from services.digest_service import DigestService
from core.logging import get_logger

router = APIRouter(prefix="/digests", tags=["digests"])
logger = get_logger(__name__)


@router.get("/latest", response_model=Optional[DigestResponse])
async def get_latest_digest(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Get the most recent digest for the current user."""
    digest_service = DigestService(db)
    digest = await digest_service.get_latest_digest(str(current_user.id))
    return digest


@router.get("/", response_model=List[DigestResponse])
async def list_digests(
    limit: int = Query(default=7, le=30),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """List recent digests for the current user."""
    digest_service = DigestService(db)
    digests = await digest_service.list_digests(str(current_user.id), limit=limit)
    return digests


@router.get("/{digest_date}", response_model=Optional[DigestResponse])
async def get_digest_by_date(
    digest_date: date,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Get a specific digest by date (YYYY-MM-DD)."""
    digest_service = DigestService(db)
    digest = await digest_service.get_digest_by_date(str(current_user.id), digest_date)

    if not digest:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Digest not found for this date")

    return digest


@router.post("/generate", response_model=DigestResponse)
async def generate_digest(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Manually generate/regenerate today's digest."""
    digest_service = DigestService(db)
    digest = await digest_service.generate_digest(str(current_user.id))

    logger.info("digest_generated_on_demand", user_id=str(current_user.id))
    return digest
