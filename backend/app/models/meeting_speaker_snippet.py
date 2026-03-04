"""Detected speaker snippet from meeting audio - for user to review and identify."""
from datetime import datetime
from typing import Optional

from sqlalchemy import DateTime, Float, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base


class MeetingSpeakerSnippet(Base):
    """
    One audio snippet from a meeting: a detected (unknown) speaker segment.
    User can listen and identify later (link to Speaker or create new).
    """

    __tablename__ = "meeting_speaker_snippets"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    meeting_id: Mapped[int] = mapped_column(ForeignKey("meetings.id"), nullable=False)
    snippet_path: Mapped[str] = mapped_column(String(512), nullable=False)
    label: Mapped[str] = mapped_column(String(64), default="Speaker")  # e.g. "Speaker 1"
    start_sec: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    end_sec: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    speaker_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("speakers.id"), nullable=True
    )  # set when user identifies
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    meeting = relationship("Meeting", back_populates="speaker_snippets")
    speaker = relationship("Speaker", back_populates="meeting_snippets")
