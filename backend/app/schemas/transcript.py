"""Transcript schemas."""
from typing import Any, Optional

from pydantic import BaseModel, ConfigDict


class TranscriptSegmentSchema(BaseModel):
    id: int
    start: float
    end: float
    text: str


class TranscriptResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    meeting_id: int
    raw_text: str
    language: Optional[str] = None
    duration_seconds: Optional[float] = None
    segments: Optional[list[dict[str, Any]]] = None  # [{id, start, end, text}, ...]
