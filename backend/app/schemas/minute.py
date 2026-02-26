"""Minute schemas."""
from typing import Any, Optional

from pydantic import BaseModel, ConfigDict


class MinuteResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    meeting_id: int
    formatted_content: dict[str, Any]
    template_id: Optional[int] = None
    model_used: Optional[str] = None
    markdown: Optional[str] = None
