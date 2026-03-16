from pydantic import BaseModel, Field
from uuid import UUID
from datetime import datetime
from typing import Optional, Dict, Any


class TaskCreateRequest(BaseModel):
    title: str
    description: Optional[str] = None
    priority: str = Field(default="normal", pattern="^(low|normal|high|urgent)$")
    due_date: Optional[datetime] = None


class TaskUpdateRequest(BaseModel):
    status: Optional[str] = Field(default=None, pattern="^(pending|in_progress|completed|dismissed)$")
    priority: Optional[str] = Field(default=None, pattern="^(low|normal|high|urgent)$")
    title: Optional[str] = None
    description: Optional[str] = None
    due_date: Optional[datetime] = None


class TaskResponse(BaseModel):
    id: UUID
    user_id: UUID
    email_id: Optional[UUID] = None
    title: str
    description: Optional[str] = None
    source: str
    status: str
    priority: str
    metadata: Dict[str, Any] = {}
    due_date: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}

    @classmethod
    def from_model(cls, t):
        return cls(
            id=t.id,
            user_id=t.user_id,
            email_id=t.email_id,
            title=t.title,
            description=t.description,
            source=t.source,
            status=t.status,
            priority=t.priority,
            metadata=t.extra_data or {},
            due_date=t.due_date,
            completed_at=t.completed_at,
            created_at=t.created_at,
            updated_at=t.updated_at,
        )
