"""User model - for auth and ownership of projects/speakers."""
from datetime import datetime
from typing import Optional

from sqlalchemy import DateTime, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base


class User(Base):
    """User entity - dummy admin for now; extend for real auth."""

    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    username: Mapped[str] = mapped_column(String(128), unique=True)
    password: Mapped[str] = mapped_column(String(256))  # plain or hash; admin uses config
    token: Mapped[Optional[str]] = mapped_column(String(256), nullable=True)  # session token for login
    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow
    )

    projects = relationship("Project", back_populates="user", cascade="all, delete-orphan")
    speakers = relationship("Speaker", back_populates="user", cascade="all, delete-orphan")
    templates = relationship("Template", back_populates="user", cascade="all, delete-orphan")
