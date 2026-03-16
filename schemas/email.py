from pydantic import BaseModel, Field
from uuid import UUID
from datetime import datetime
from typing import Optional, List, Dict, Any


class EmailClassification(BaseModel):
    urgent: bool
    needs_response: bool
    category: str
    confidence: float = Field(ge=0.0, le=1.0)
    reasoning: Optional[str] = None


class EmailResponse(BaseModel):
    id: UUID
    user_id: UUID
    gmail_message_id: str
    thread_id: str
    subject: str
    sender: str
    recipients: List[str]
    cc: List[str] = Field(default_factory=list)
    bcc: List[str] = Field(default_factory=list)
    body: str
    html_body: Optional[str] = None
    classification: Optional[EmailClassification] = None
    received_at: datetime
    created_at: datetime
    updated_at: datetime
    extra_data: Dict[str, Any] = Field(default_factory=dict, serialization_alias="metadata")

    model_config = {"from_attributes": True}
