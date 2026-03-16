from pydantic import BaseModel, Field
from uuid import UUID
from datetime import date, datetime
from typing import Optional, Dict, List


class UrgentEmailSummary(BaseModel):
    id: str
    subject: str
    sender: str
    received_at: str
    has_pending_suggestion: bool = False


class SuggestionsSummary(BaseModel):
    total: int = 0
    accepted: int = 0
    rejected: int = 0
    pending: int = 0


class DigestContent(BaseModel):
    total_emails: int = 0
    category_breakdown: Dict[str, int] = Field(default_factory=dict)
    urgent_emails: List[UrgentEmailSummary] = Field(default_factory=list)
    suggestions_summary: SuggestionsSummary = Field(default_factory=SuggestionsSummary)
    period_start: str
    period_end: str


class DigestResponse(BaseModel):
    id: UUID
    user_id: UUID
    digest_date: date
    content: DigestContent
    llm_summary: Optional[str] = None
    status: str
    created_at: datetime

    model_config = {"from_attributes": True}
