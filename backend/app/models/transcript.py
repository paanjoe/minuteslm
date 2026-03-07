"""Transcript model - raw ASR output with optional segment-level data."""
from typing import Any, Optional

from sqlalchemy import Float, ForeignKey, String, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base


class Transcript(Base):
    """Raw transcript from ASR. segments: list of {id, start, end, text} for timestamped view."""

    __tablename__ = "transcripts"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    meeting_id: Mapped[int] = mapped_column(ForeignKey("meetings.id"))
    raw_text: Mapped[str] = mapped_column(Text)
    language: Mapped[Optional[str]] = mapped_column(String(16), nullable=True)
    duration_seconds: Mapped[Optional[float]] = mapped_column(
        Float, nullable=True
    )
    segments: Mapped[Optional[list[dict[str, Any]]]] = mapped_column(
        JSONB, nullable=True
    )  # [{id, start, end, text}, ...]

    meeting = relationship("Meeting", back_populates="transcript")
