from pydantic import BaseModel, Field
from uuid import UUID
from datetime import datetime
from typing import Dict, Any, Optional


class StyleProfileData(BaseModel):
    tone: Optional[str] = None
    formality: Optional[str] = None
    avg_length: Optional[int] = None
    greeting_patterns: list[str] = Field(default_factory=list)
    signoff_patterns: list[str] = Field(default_factory=list)
    emoji_usage: float = 0.0
    common_phrases: list[str] = Field(default_factory=list)
    response_speed: Optional[str] = None


class StyleProfileResponse(BaseModel):
    id: UUID
    user_id: UUID
    profile_json: Dict[str, Any]
    sample_size: int
    version: int
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}
