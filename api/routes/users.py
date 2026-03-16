from fastapi import APIRouter, Depends, HTTPException, status, Response
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, delete
from db.session import get_db
from models.user import User
from models.email import Email
from models.suggestion import Suggestion
from models.embedding import Embedding
from models.feedback_log import FeedbackLog
from models.style_profile import StyleProfile
from schemas.user import UserResponse, UserUpdate
from api.deps import get_current_user
from core.logging import get_logger
import json

router = APIRouter(prefix="/users", tags=["users"])
logger = get_logger(__name__)


@router.get("/me", response_model=UserResponse)
async def get_current_user_info(
    current_user: User = Depends(get_current_user)
):
    return current_user


@router.patch("/me", response_model=UserResponse)
async def update_current_user(
    user_update: UserUpdate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    if user_update.autonomy_level is not None:
        current_user.autonomy_level = user_update.autonomy_level

    if user_update.token_budget is not None:
        current_user.token_budget = user_update.token_budget

    await db.commit()
    await db.refresh(current_user)

    logger.info("user_updated", user_id=str(current_user.id))

    return current_user


@router.post("/me/onboarding/complete", response_model=UserResponse)
async def complete_onboarding(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Mark the current user's onboarding as complete."""
    metadata = dict(current_user.extra_data or {})
    metadata["onboarding_completed"] = True
    current_user.extra_data = metadata

    await db.commit()
    await db.refresh(current_user)

    logger.info("onboarding_completed", user_id=str(current_user.id))

    return current_user


@router.get("/me/export")
async def export_user_data(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    emails_result = await db.execute(
        select(Email).where(Email.user_id == current_user.id)
    )
    emails = emails_result.scalars().all()

    suggestions_result = await db.execute(
        select(Suggestion).where(Suggestion.user_id == current_user.id)
    )
    suggestions = suggestions_result.scalars().all()

    feedback_result = await db.execute(
        select(FeedbackLog).where(FeedbackLog.user_id == current_user.id)
    )
    feedback_logs = feedback_result.scalars().all()

    style_result = await db.execute(
        select(StyleProfile).where(StyleProfile.user_id == current_user.id)
    )
    style_profile = style_result.scalar_one_or_none()

    export_data = {
        "user": {
            "id": str(current_user.id),
            "email": current_user.email,
            "autonomy_level": current_user.autonomy_level,
            "created_at": current_user.created_at.isoformat()
        },
        "emails": [
            {
                "id": str(e.id),
                "subject": e.subject,
                "sender": e.sender,
                "body": e.body,
                "classification": e.classification,
                "received_at": e.received_at.isoformat()
            }
            for e in emails
        ],
        "suggestions": [
            {
                "id": str(s.id),
                "suggestion_text": s.suggestion_text,
                "confidence_score": s.confidence_score,
                "feedback_type": s.feedback_type,
                "created_at": s.created_at.isoformat()
            }
            for s in suggestions
        ],
        "feedback_logs": [
            {
                "id": str(f.id),
                "feedback_type": f.feedback_type,
                "diff_score": f.diff_score,
                "timestamp": f.timestamp.isoformat()
            }
            for f in feedback_logs
        ],
        "style_profile": style_profile.profile_json if style_profile else None
    }

    logger.info("user_data_exported", user_id=str(current_user.id))

    return Response(
        content=json.dumps(export_data, indent=2),
        media_type="application/json",
        headers={"Content-Disposition": f"attachment; filename=echo_export_{current_user.id}.json"}
    )


@router.delete("/me")
async def delete_user_account(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    await db.delete(current_user)
    await db.commit()

    logger.info("user_deleted", user_id=str(current_user.id))

    return {"status": "deleted", "message": "User account and all associated data have been permanently deleted"}
