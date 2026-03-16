from pydantic import BaseModel, ConfigDict
from typing import List, Optional, Dict, Any
from datetime import datetime
from uuid import UUID


class CalendarCreateRequest(BaseModel):
    summary: str
    start_time: datetime
    end_time: datetime
    attendees: List[str] = []
    location: Optional[str] = None
    description: Optional[str] = None


class CalendarRescheduleRequest(BaseModel):
    new_start_time: datetime
    new_end_time: datetime


class CalendarEventResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    user_id: UUID
    email_id: Optional[UUID] = None
    google_event_id: str
    summary: str
    start_time: datetime
    end_time: datetime
    attendees: List[str] = []
    location: Optional[str] = None
    status: str
    action_type: str
    llm_extraction: Dict[str, Any] = {}
    created_at: datetime
    updated_at: datetime


class CalendarProcessResponse(BaseModel):
    has_meeting: bool
    action: Optional[str] = None
    calendar_event: Optional[CalendarEventResponse] = None
    message: str
    suggested_reply: Optional[str] = None
    has_conflict: Optional[bool] = None
    free_slots: Optional[List[Dict[str, Any]]] = None
