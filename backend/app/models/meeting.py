"""Meeting model."""
import enum
from datetime import datetime
from typing import Optional

from sqlalchemy import DateTime, Enum, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base


class MeetingStatus(str, enum.Enum):
    """Meeting processing status."""

    RECORDING = "recording"
    TRANSCRIBING = "transcribing"
    FORMATTING = "formatting"
    FORMATTED = "formatted"
    ERROR = "error"


class Meeting(Base):
    """Meeting entity - one per recorded session."""

    __tablename__ = "meetings"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    title: Mapped[str] = mapped_column(String(255), default="Untitled Meeting")
    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow
    )
    audio_path: Mapped[Optional[str]] = mapped_column(String(512), nullable=True)
    status: Mapped[MeetingStatus] = mapped_column(
        Enum(MeetingStatus), default=MeetingStatus.RECORDING
    )
    error_message: Mapped[Optional[str]] = mapped_column(
        String(1024), nullable=True
    )

    transcript = relationship("Transcript", back_populates="meeting", uselist=False)
    minutes = relationship("Minute", back_populates="meeting", uselist=False)
    action_items = relationship(
        "ActionItem", back_populates="meeting", cascade="all, delete-orphan"
    )
