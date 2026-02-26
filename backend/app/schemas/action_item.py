"""Action item schemas."""
from datetime import date
from typing import Optional

from pydantic import BaseModel, ConfigDict


class ActionItemResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    meeting_id: int
    description: str
    assignee: Optional[str] = None
    due_date: Optional[date] = None
    status: str


class ActionItemCreate(BaseModel):
    description: str
    assignee: Optional[str] = None
    due_date: Optional[date] = None
    status: str = "pending"
