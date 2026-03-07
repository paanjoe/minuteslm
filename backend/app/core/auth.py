"""Simple auth: config admin or DB users with session token."""
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.database import get_db
from app.models import User

security = HTTPBearer(auto_error=False)


def verify_dummy_login(username: str, password: str) -> bool:
    """Check against dummy admin credentials from config."""
    return (
        username == settings.admin_username
        and password == settings.admin_password
    )


def get_current_user_id(
    credentials: HTTPAuthorizationCredentials | None = Depends(security),
    db: Session = Depends(get_db),
) -> int:
    """Resolve Bearer token to user id: config admin_token -> 1, else lookup User by token."""
    if not credentials or not credentials.credentials:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated",
            headers={"WWW-Authenticate": "Bearer"},
        )
    token = credentials.credentials
    if token == settings.admin_token:
        return 1
    user = db.query(User).filter(User.token == token).first()
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return user.id
