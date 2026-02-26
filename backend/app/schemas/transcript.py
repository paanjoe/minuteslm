"""Transcript schemas."""
from typing import Optional

from pydantic import BaseModel, ConfigDict


class TranscriptResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    meeting_id: int
    raw_text: str
    language: Optional[str] = None
    duration_seconds: Optional[float] = None
