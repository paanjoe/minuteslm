"""Minute model - formatted meeting minutes."""
from typing import Optional

from sqlalchemy import ForeignKey, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base


class Minute(Base):
    """Formatted meeting minutes from LLM."""

    __tablename__ = "minutes"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    meeting_id: Mapped[int] = mapped_column(ForeignKey("meetings.id"))
    formatted_content: Mapped[dict] = mapped_column(JSONB)
    template_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("templates.id"), nullable=True
    )
    model_used: Mapped[Optional[str]] = mapped_column(String(128), nullable=True)
    markdown: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    meeting = relationship("Meeting", back_populates="minutes")
    template = relationship("Template", back_populates="minutes")
