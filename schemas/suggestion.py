from pydantic import BaseModel, Field
from uuid import UUID
from datetime import datetime
from typing import Optional, Dict, Any


class SuggestionCreate(BaseModel):
    email_id: UUID
    suggestion_text: str
    confidence_score: float = Field(ge=0.0, le=1.0)
    reasoning: Optional[str] = None


class SuggestionFeedback(BaseModel):
    feedback_type: str = Field(pattern="^(accepted|edited|rejected)$")
    final_text: Optional[str] = None


class SuggestionResponse(BaseModel):
    id: UUID
    email_id: UUID
    user_id: UUID
    suggestion_text: str
    final_text: Optional[str] = None
    feedback_type: Optional[str] = None
    confidence_score: float
    status: str
    reasoning: Optional[str] = None
    created_at: datetime
    updated_at: datetime
    context_used: Dict[str, Any] = Field(default_factory=dict)
    extra_data: Dict[str, Any] = Field(default_factory=dict, serialization_alias="metadata")

    model_config = {"from_attributes": True}
