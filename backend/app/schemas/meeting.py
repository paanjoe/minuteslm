"""Meeting schemas."""
from datetime import datetime
from enum import Enum
from typing import Optional

from pydantic import BaseModel, ConfigDict


class MeetingStatus(str, Enum):
    RECORDING = "recording"
    TRANSCRIBING = "transcribing"
    TRANSCRIBED = "transcribed"
    FORMATTING = "formatting"
    FORMATTED = "formatted"
    ERROR = "error"


class MeetingCreate(BaseModel):
    title: str = "Untitled Meeting"
    project_id: int
    discussion_date_time: Optional[datetime] = None
    attendee: Optional[str] = None
    absentees: Optional[str] = None
    minutes_taken_by: Optional[str] = None
    summary_context: Optional[str] = None


class MeetingUpdate(BaseModel):
    title: Optional[str] = None
    template_id: Optional[int] = None
    discussion_date_time: Optional[datetime] = None
    attendee: Optional[str] = None
    absentees: Optional[str] = None
    minutes_taken_by: Optional[str] = None
    summary_context: Optional[str] = None


class MeetingResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    project_id: Optional[int] = None
    title: str
    template_id: Optional[int] = None
    created_at: datetime
    audio_path: Optional[str] = None
    status: MeetingStatus
    error_message: Optional[str] = None
    progress_message: Optional[str] = None
    progress_percentage: Optional[int] = None  # 0-100 when in progress
    discussion_date_time: Optional[datetime] = None
    attendee: Optional[str] = None
    absentees: Optional[str] = None
    minutes_taken_by: Optional[str] = None
    summary_context: Optional[str] = None


class MeetingListResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    project_id: Optional[int] = None
    title: str
    template_id: Optional[int] = None
    created_at: datetime
    status: MeetingStatus
    discussion_date_time: Optional[datetime] = None
    attendee: Optional[str] = None
    absentees: Optional[str] = None
    minutes_taken_by: Optional[str] = None
    summary_context: Optional[str] = None
