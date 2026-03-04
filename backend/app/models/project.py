"""Project model - one per user, contains many meetings."""
from datetime import datetime
from typing import Optional

from sqlalchemy import DateTime, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base


class Project(Base):
    """Project entity - belongs to a user, has many meetings."""

    __tablename__ = "projects"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)
    name: Mapped[str] = mapped_column(String(255), default="Untitled Project")
    default_template_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("templates.id"), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow
    )

    user = relationship("User", back_populates="projects")
    meetings = relationship(
        "Meeting", back_populates="project", cascade="all, delete-orphan"
    )
    templates = relationship(
        "Template",
        back_populates="project",
        foreign_keys="Template.project_id",
    )
    default_template = relationship(
        "Template",
        foreign_keys=[default_template_id],
        uselist=False,
    )
