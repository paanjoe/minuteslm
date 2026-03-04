"""Speaker model - voice sample + label for 'who is this guy'."""
from datetime import datetime
from typing import Optional

from sqlalchemy import DateTime, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base


class Speaker(Base):
    """Speaker profile: name + sample audio for future diarization."""

    __tablename__ = "speakers"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)
    name: Mapped[str] = mapped_column(String(255))
    audio_path: Mapped[Optional[str]] = mapped_column(String(512), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow
    )

    user = relationship("User", back_populates="speakers")
    meeting_snippets = relationship(
        "MeetingSpeakerSnippet", back_populates="speaker"
    )
