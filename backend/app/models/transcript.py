"""Transcript model - raw ASR output."""
from typing import Optional

from sqlalchemy import Float, ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base


class Transcript(Base):
    """Raw transcript from ASR."""

    __tablename__ = "transcripts"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    meeting_id: Mapped[int] = mapped_column(ForeignKey("meetings.id"))
    raw_text: Mapped[str] = mapped_column(Text)
    language: Mapped[Optional[str]] = mapped_column(String(16), nullable=True)
    duration_seconds: Mapped[Optional[float]] = mapped_column(
        Float, nullable=True
    )

    meeting = relationship("Meeting", back_populates="transcript")
