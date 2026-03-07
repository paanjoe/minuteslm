"""User management API - admin only; default admin cannot be removed."""
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from pydantic import BaseModel

from app.core.auth import get_current_user_id
from app.core.config import settings
from app.core.database import get_db
from app.models import User

router = APIRouter(prefix="/users", tags=["users"])


def _protected_username() -> str:
    return settings.admin_username


def _require_admin(user_id: int) -> None:
    if user_id != 1:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only admin can manage users",
        )


class UserListItem(BaseModel):
    id: int
    username: str
    created_at: str
    is_protected: bool


class UserCreatePayload(BaseModel):
    username: str
    password: str


@router.get("", response_model=list[UserListItem])
def list_users(
    user_id: int = Depends(get_current_user_id),
    db: Session = Depends(get_db),
):
    """List all users. Admin only."""
    _require_admin(user_id)
    users = db.query(User).order_by(User.id).all()
    protected = _protected_username()
    return [
        UserListItem(
            id=u.id,
            username=u.username,
            created_at=u.created_at.isoformat() if u.created_at else "",
            is_protected=(u.username == protected),
        )
        for u in users
    ]


@router.post("", response_model=UserListItem)
def create_user(
    payload: UserCreatePayload,
    user_id: int = Depends(get_current_user_id),
    db: Session = Depends(get_db),
):
    """Create a new user (colleague). Admin only. Cannot create username same as default admin."""
    _require_admin(user_id)
    username = payload.username.strip()
    if not username:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Username required")
    if username == _protected_username():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot create user with the default admin username",
        )
    if db.query(User).filter(User.username == username).first():
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Username already exists")
    user = User(username=username, password=payload.password)
    db.add(user)
    db.commit()
    db.refresh(user)
    return UserListItem(
        id=user.id,
        username=user.username,
        created_at=user.created_at.isoformat() if user.created_at else "",
        is_protected=(user.username == _protected_username()),
    )


@router.delete("/{target_id}")
def delete_user(
    target_id: int,
    current_user_id: int = Depends(get_current_user_id),
    db: Session = Depends(get_db),
):
    """Delete a user. Admin only. Cannot delete the default admin (admin with default pw)."""
    _require_admin(current_user_id)
    user = db.query(User).filter(User.id == target_id).first()
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
    if user.username == _protected_username():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot remove the default admin user",
        )
    db.delete(user)
    db.commit()
    return {"ok": True}
