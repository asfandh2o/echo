from pydantic import BaseModel, EmailStr, Field, model_validator
from uuid import UUID
from datetime import datetime
from typing import Optional, Dict, Any


class UserCreate(BaseModel):
    email: EmailStr
    autonomy_level: str = "supervised"


class UserUpdate(BaseModel):
    autonomy_level: Optional[str] = None
    token_budget: Optional[int] = None


class UserResponse(BaseModel):
    id: UUID
    email: str
    autonomy_level: str
    token_budget: int
    tokens_used_today: int
    onboarding_completed: bool = False
    created_at: datetime
    updated_at: datetime
    extra_data: Dict[str, Any] = Field(default_factory=dict, serialization_alias="metadata")

    model_config = {"from_attributes": True}

    @model_validator(mode="before")
    @classmethod
    def extract_onboarding_status(cls, data):
        if hasattr(data, "extra_data") and isinstance(data.extra_data, dict):
            data.__dict__["onboarding_completed"] = data.extra_data.get("onboarding_completed", False)
        elif isinstance(data, dict):
            metadata = data.get("extra_data") or data.get("metadata") or {}
            data["onboarding_completed"] = metadata.get("onboarding_completed", False)
        return data
