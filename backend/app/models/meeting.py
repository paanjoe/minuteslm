"""Meeting model."""
import enum
from datetime import datetime
from typing import Optional

from sqlalchemy import DateTime, Enum, ForeignKey, String
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
    project_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("projects.id"), nullable=True
    )
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
    template_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("templates.id"), nullable=True
    )

    project = relationship("Project", back_populates="meetings")
    template = relationship("Template", foreign_keys=[template_id], uselist=False)
    transcript = relationship(
        "Transcript", back_populates="meeting", uselist=False, cascade="all, delete-orphan"
    )
    minutes = relationship(
        "Minute", back_populates="meeting", uselist=False, cascade="all, delete-orphan"
    )
    action_items = relationship(
        "ActionItem", back_populates="meeting", cascade="all, delete-orphan"
    )
    speaker_snippets = relationship(
        "MeetingSpeakerSnippet", back_populates="meeting", cascade="all, delete-orphan"
    )
