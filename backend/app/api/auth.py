"""Auth API - dummy login for admin."""
from fastapi import APIRouter, HTTPException, status


from app.core.auth import verify_dummy_login
from app.core.config import settings
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
def login(payload: LoginRequest):
    """Dummy login: admin / admin. Replace with real auth later."""
    if not verify_dummy_login(payload.username, payload.password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid username or password",
        )
    return LoginResponse(
        access_token=settings.admin_token,
        user=UserResponse(id=1, username=settings.admin_username),
    )
