from typing import Dict, Any, List, Optional
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, desc
from models.task import Task
from models.email import Email
from services.llm_router import llm_router
from core.logging import get_logger
from datetime import datetime

logger = get_logger(__name__)


class TaskService:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def extract_tasks_from_email(self, email_id: str, user_id: str) -> List[Task]:
        """Extract and create tasks from an email using LLM."""
        existing = await self.db.execute(
            select(Task).where(Task.email_id == email_id, Task.user_id == user_id)
        )
        if existing.scalars().first():
            logger.info("tasks_already_extracted", email_id=email_id)
            return []

        result = await self.db.execute(select(Email).where(Email.id == email_id))
        email = result.scalar_one_or_none()
        if not email:
            raise ValueError(f"Email {email_id} not found")

        extraction = await llm_router.extract_tasks(
            email_content=email.body,
            subject=email.subject,
            sender=email.sender,
        )

        if not extraction.get("has_tasks"):
            return []

        created_tasks = []
        for task_data in extraction.get("tasks", []):
            due_date = None
            if task_data.get("due_date"):
                try:
                    due_date = datetime.fromisoformat(task_data["due_date"])
                except (ValueError, TypeError):
                    pass

            task = Task(
                user_id=user_id,
                email_id=email_id,
                title=task_data["title"],
                description=task_data.get("reasoning"),
                source="echo",
                status="pending",
                priority=task_data.get("priority", "normal"),
                due_date=due_date,
                extra_data={
                    "email_subject": email.subject,
                    "email_sender": email.sender,
                    "extraction_reasoning": task_data.get("reasoning"),
                },
            )
            self.db.add(task)
            created_tasks.append(task)

        if created_tasks:
            await self.db.commit()
            for t in created_tasks:
                await self.db.refresh(t)
            logger.info("tasks_created_from_email", email_id=email_id, count=len(created_tasks))

        return created_tasks

    async def create_task_from_hera(self, user_id: str, hera_data: Dict[str, Any]) -> Task:
        """Create a task from a HERA webhook notification."""
        due_date = None
        if hera_data.get("deadline"):
            try:
                due_date = datetime.fromisoformat(hera_data["deadline"])
            except (ValueError, TypeError):
                pass

        task = Task(
            user_id=user_id,
            title=hera_data.get("title", "HERA Task"),
            description=hera_data.get("description"),
            source="hera",
            status="pending",
            priority=hera_data.get("priority", "normal"),
            due_date=due_date,
            extra_data={
                "hera_task_id": hera_data.get("task_id"),
                "project_name": hera_data.get("project_name"),
                "assigned_by": hera_data.get("assigned_by"),
            },
        )
        self.db.add(task)
        await self.db.commit()
        await self.db.refresh(task)
        return task

    async def create_manual_task(
        self, user_id: str, title: str, description: str = None,
        priority: str = "normal", due_date: datetime = None,
    ) -> Task:
        """Create a user-created manual task."""
        task = Task(
            user_id=user_id,
            title=title,
            description=description,
            source="manual",
            status="pending",
            priority=priority,
            due_date=due_date,
        )
        self.db.add(task)
        await self.db.commit()
        await self.db.refresh(task)
        return task

    async def list_tasks(
        self, user_id: str, status_filter: str = None,
        source_filter: str = None, limit: int = 50,
    ) -> List[Task]:
        query = select(Task).where(Task.user_id == user_id)
        if status_filter:
            query = query.where(Task.status == status_filter)
        if source_filter:
            query = query.where(Task.source == source_filter)
        query = query.order_by(desc(Task.created_at)).limit(limit)

        result = await self.db.execute(query)
        return result.scalars().all()

    async def update_task(self, task_id: str, user_id: str, updates: Dict[str, Any]) -> Task:
        result = await self.db.execute(
            select(Task).where(Task.id == task_id, Task.user_id == user_id)
        )
        task = result.scalar_one_or_none()
        if not task:
            raise ValueError(f"Task {task_id} not found")

        for key, value in updates.items():
            if key in ("status", "priority", "title", "description", "due_date") and value is not None:
                setattr(task, key, value)

        if updates.get("status") == "completed":
            task.completed_at = datetime.utcnow()
        elif updates.get("status") and updates["status"] != "completed":
            task.completed_at = None

        await self.db.commit()
        await self.db.refresh(task)
        return task

    async def delete_task(self, task_id: str, user_id: str) -> bool:
        result = await self.db.execute(
            select(Task).where(Task.id == task_id, Task.user_id == user_id)
        )
        task = result.scalar_one_or_none()
        if not task:
            return False
        await self.db.delete(task)
        await self.db.commit()
        return True
