from pydantic import BaseModel, Field
from uuid import UUID
from datetime import datetime
from typing import Optional, Dict, Any, List


class NotificationResponse(BaseModel):
    id: UUID
    user_id: UUID
    type: str
    source: str
    title: str
    message: Optional[str] = None
    read: bool
    metadata: Dict[str, Any] = {}
    action_type: Optional[str] = None
    action_status: Optional[str] = None
    action_payload: Optional[Dict[str, Any]] = None
    created_at: datetime

    model_config = {"from_attributes": True}

    @classmethod
    def from_model(cls, n):
        return cls(
            id=n.id,
            user_id=n.user_id,
            type=n.type,
            source=n.source,
            title=n.title,
            message=n.message,
            read=n.read,
            metadata=n.extra_data or {},
            action_type=n.action_type,
            action_status=n.action_status,
            action_payload=n.action_payload,
            created_at=n.created_at,
        )


class NotificationActionRequest(BaseModel):
    action: str = Field(pattern="^(confirm|dismiss)$")


class WebhookNotification(BaseModel):
    """Payload from external services (HERA) to create notifications."""
    email: str  # user's email to match
    type: str = "info"
    source: str = "hera"
    title: str
    message: Optional[str] = None
    metadata: Dict[str, Any] = {}


class WebhookBatchRequest(BaseModel):
    """Batch of notifications from external services."""
    api_key: str
    notifications: List[WebhookNotification]
