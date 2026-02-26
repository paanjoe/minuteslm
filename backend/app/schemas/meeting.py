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


class MeetingResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    title: str
    created_at: datetime
    audio_path: Optional[str] = None
    status: MeetingStatus
    error_message: Optional[str] = None


class MeetingListResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    title: str
    created_at: datetime
    status: MeetingStatus
