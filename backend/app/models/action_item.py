"""Action item model - extracted tasks."""
from datetime import date
from typing import Optional

from sqlalchemy import Date, ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base


class ActionItem(Base):
    """Action item extracted from meeting."""

    __tablename__ = "action_items"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    meeting_id: Mapped[int] = mapped_column(ForeignKey("meetings.id"))
    description: Mapped[str] = mapped_column(Text)
    assignee: Mapped[Optional[str]] = mapped_column(String(256), nullable=True)
    due_date: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    status: Mapped[str] = mapped_column(String(32), default="pending")

    meeting = relationship("Meeting", back_populates="action_items")
