"""Speaker schemas."""
from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict


class SpeakerCreate(BaseModel):
    name: str


class SpeakerResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    user_id: int
    name: str
    audio_path: Optional[str] = None
    created_at: datetime
