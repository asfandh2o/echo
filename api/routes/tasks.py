from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from typing import List, Optional
from uuid import UUID
import httpx
from db.session import get_db
from models.user import User
from models.task import Task
from schemas.task import TaskCreateRequest, TaskUpdateRequest, TaskResponse
from api.deps import get_current_user
from services.task_service import TaskService
from core.config import settings
from core.logging import get_logger

router = APIRouter(prefix="/tasks", tags=["tasks"])
logger = get_logger(__name__)


@router.get("/", response_model=List[TaskResponse])
async def list_tasks(
    status_filter: Optional[str] = None,
    source_filter: Optional[str] = None,
    limit: int = 50,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """List tasks for the current user."""
    task_service = TaskService(db)
    tasks = await task_service.list_tasks(
        str(current_user.id),
        status_filter=status_filter,
        source_filter=source_filter,
        limit=limit,
    )
    return [TaskResponse.from_model(t) for t in tasks]


@router.post("/", response_model=TaskResponse)
async def create_task(
    request: TaskCreateRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Manually create a task."""
    task_service = TaskService(db)
    task = await task_service.create_manual_task(
        user_id=str(current_user.id),
        title=request.title,
        description=request.description,
        priority=request.priority,
        due_date=request.due_date,
    )
    return TaskResponse.from_model(task)


@router.patch("/{task_id}", response_model=TaskResponse)
async def update_task(
    task_id: UUID,
    request: TaskUpdateRequest,
    background_tasks: BackgroundTasks,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Update a task (status, priority, etc.)."""
    task_service = TaskService(db)
    try:
        task = await task_service.update_task(
            str(task_id), str(current_user.id),
            request.model_dump(exclude_none=True),
        )

        # Sync status back to HERA if it's a HERA task
        if request.status and task.extra_data and task.extra_data.get("hera_task_id"):
            background_tasks.add_task(
                _sync_to_hera,
                task.extra_data["hera_task_id"],
                request.status,
            )

        return TaskResponse.from_model(task)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.delete("/{task_id}")
async def delete_task(
    task_id: UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Delete a task."""
    task_service = TaskService(db)
    deleted = await task_service.delete_task(str(task_id), str(current_user.id))
    if not deleted:
        raise HTTPException(status_code=404, detail="Task not found")
    return {"status": "deleted"}


@router.post("/sync", summary="Receive task status updates from HERA")
async def receive_hera_sync(
    body: dict,
    db: AsyncSession = Depends(get_db),
):
    """Webhook for HERA to sync task status changes to ECHO."""
    if body.get("api_key") != settings.SECRET_KEY:
        raise HTTPException(status_code=401, detail="Invalid API key")

    hera_task_id = body.get("hera_task_id")
    email = body.get("email")
    new_status = body.get("status")
    if not hera_task_id or not new_status:
        raise HTTPException(status_code=400, detail="Missing hera_task_id or status")

    # Map HERA statuses to ECHO statuses
    status_map = {
        "pending": "pending",
        "assigned": "pending",
        "in_progress": "in_progress",
        "done": "completed",
    }
    echo_status = status_map.get(new_status, new_status)

    # Find ECHO task by hera_task_id in metadata
    from sqlalchemy.dialects.postgresql import JSONB
    result = await db.execute(
        select(Task).where(
            Task.source == "hera",
            Task.extra_data["hera_task_id"].astext == hera_task_id,
        )
    )
    task = result.scalar_one_or_none()
    if not task:
        logger.warning("hera_sync_task_not_found", hera_task_id=hera_task_id)
        return {"status": "not_found"}

    from datetime import datetime
    task.status = echo_status
    if echo_status == "completed":
        task.completed_at = datetime.utcnow()
    elif task.completed_at:
        task.completed_at = None

    # Sync deadline if provided
    deadline_str = body.get("deadline")
    if deadline_str:
        try:
            task.due_date = datetime.fromisoformat(deadline_str)
        except (ValueError, TypeError):
            pass

    await db.commit()
    logger.info("echo_task_synced_from_hera", hera_task_id=hera_task_id, status=echo_status)
    return {"status": "ok", "echo_status": echo_status}


async def _sync_to_hera(hera_task_id: str, echo_status: str):
    """Sync an ECHO task status change back to HERA."""
    if not settings.HERA_API_URL or not settings.HERA_API_KEY:
        return
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.post(
                f"{settings.HERA_API_URL}/tasks/sync",
                json={
                    "api_key": settings.HERA_API_KEY,
                    "hera_task_id": hera_task_id,
                    "status": echo_status,
                },
            )
            if resp.status_code == 200:
                logger.info("hera_sync_sent", hera_task_id=hera_task_id, status=echo_status)
            else:
                logger.warning("hera_sync_failed", status=resp.status_code, body=resp.text)
    except Exception as e:
        logger.warning("hera_sync_error", error=str(e))
