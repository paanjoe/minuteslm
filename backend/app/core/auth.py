"""Simple auth for dummy admin login. Replace with proper auth later."""
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from app.core.config import settings

security = HTTPBearer(auto_error=False)


def verify_dummy_login(username: str, password: str) -> bool:
    """Check against dummy admin credentials."""
    return (
        username == settings.admin_username
        and password == settings.admin_password
    )


def get_current_user_id(
    credentials: HTTPAuthorizationCredentials | None = Depends(security),
) -> int:
    """Require Bearer token; dummy auth uses fixed token matching admin."""
    if not credentials or credentials.credentials != settings.admin_token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return 1  # Dummy admin user id
