"""Auth API - login for admin (config) or DB users."""
import secrets

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.core.auth import verify_dummy_login
from app.core.config import settings
from app.core.database import get_db
from app.models import User
from pydantic import BaseModel

router = APIRouter(prefix="/auth", tags=["auth"])


class LoginRequest(BaseModel):
    username: str
    password: str


class UserResponse(BaseModel):
    id: int
    username: str


class LoginResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: UserResponse


@router.post("/login", response_model=LoginResponse)
def login(payload: LoginRequest, db: Session = Depends(get_db)):
    """Login: config admin (e.g. admin/admin) or any DB user by username/password."""
    if verify_dummy_login(payload.username, payload.password):
        return LoginResponse(
            access_token=settings.admin_token,
            user=UserResponse(id=1, username=settings.admin_username),
        )
    user = db.query(User).filter(User.username == payload.username.strip()).first()
    if not user or user.password != payload.password:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid username or password",
        )
    token = secrets.token_urlsafe(32)
    user.token = token
    db.commit()
    return LoginResponse(
        access_token=token,
        user=UserResponse(id=user.id, username=user.username),
    )
