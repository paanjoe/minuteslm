"""Project schemas."""
from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict


class ProjectCreate(BaseModel):
    name: str = "Untitled Project"


class ProjectUpdate(BaseModel):
    name: Optional[str] = None
    default_template_id: Optional[int] = None


class ProjectResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    user_id: int
    name: str
    default_template_id: Optional[int] = None
    created_at: datetime


class ProjectListResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    default_template_id: Optional[int] = None
    created_at: datetime
