"""Meeting schemas."""
from datetime import datetime
from enum import Enum
from typing import Optional

from pydantic import BaseModel, ConfigDict


class MeetingStatus(str, Enum):
    RECORDING = "recording"
    TRANSCRIBING = "transcribing"
    FORMATTING = "formatting"
    FORMATTED = "formatted"
    ERROR = "error"


class MeetingCreate(BaseModel):
    title: str = "Untitled Meeting"
    project_id: int


class MeetingUpdate(BaseModel):
    title: Optional[str] = None
    template_id: Optional[int] = None


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


class MeetingListResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    project_id: Optional[int] = None
    title: str
    template_id: Optional[int] = None
    created_at: datetime
    status: MeetingStatus
