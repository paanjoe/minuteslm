"""Template model - configurable output format (tied to user/project)."""
from typing import List, Optional

from sqlalchemy import ForeignKey, String, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base


# Default structure matching the standard minutes format
DEFAULT_STRUCTURE = {
    "overview": "Overview",
    "discussion_highlights": "Discussion Highlights",
    "action_items": "Action Items",
    "key_decisions": "Key Decisions",
}


class Template(Base):
    """Template for meeting minutes format. Owned by user; optionally tied to a project."""

    __tablename__ = "templates"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)
    project_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("projects.id"), nullable=True
    )
    name: Mapped[str] = mapped_column(String(128))
    structure: Mapped[dict] = mapped_column(
        JSONB, default=lambda: dict(DEFAULT_STRUCTURE)
    )
    prompt_suffix: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    file_path: Mapped[Optional[str]] = mapped_column(String(512), nullable=True)
    file_name: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    sample_content: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    section_titles: Mapped[Optional[List[str]]] = mapped_column(JSONB, nullable=True)
    is_default: Mapped[bool] = mapped_column(default=False)

    user = relationship("User", back_populates="templates")
    project = relationship(
        "Project",
        back_populates="templates",
        foreign_keys=[project_id],
    )
    minutes = relationship("Minute", back_populates="template")
