"""Schemas for detected meeting speaker snippets."""
from datetime import datetime
from typing import Optional

from pydantic import ConfigDict, BaseModel


class MeetingSpeakerSnippetResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    meeting_id: int
    snippet_path: str
    label: str
    start_sec: Optional[float] = None
    end_sec: Optional[float] = None
    speaker_id: Optional[int] = None
    created_at: datetime


class IdentifySpeakerRequest(BaseModel):
    speaker_id: Optional[int] = None  # link to existing
    name: Optional[str] = None  # create new speaker and link
