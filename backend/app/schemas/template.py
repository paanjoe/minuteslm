"""Template schemas."""
from typing import Any, List, Optional

from pydantic import BaseModel, ConfigDict


class TemplateCreate(BaseModel):
    name: str
    project_id: Optional[int] = None
    prompt_suffix: Optional[str] = None
    structure: Optional[dict[str, Any]] = None


class TemplateUpdate(BaseModel):
    name: Optional[str] = None
    project_id: Optional[int] = None
    prompt_suffix: Optional[str] = None
    structure: Optional[dict[str, Any]] = None


class TemplateResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    user_id: int
    project_id: Optional[int] = None
    name: str
    structure: dict[str, Any]
    prompt_suffix: Optional[str] = None
    file_path: Optional[str] = None
    file_name: Optional[str] = None
    section_titles: Optional[List[str]] = None
    is_default: bool


class TemplateListResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    project_id: Optional[int] = None
    name: str
    file_name: Optional[str] = None
    section_titles: Optional[List[str]] = None
    is_default: bool
