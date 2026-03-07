"""API to purge all user data (auth required)."""
from fastapi import APIRouter, Depends

from app.core.auth import get_current_user_id
from app.core.config import settings
from app.core.database import get_db
from app.services.purge import purge_all_data
from sqlalchemy.orm import Session

router = APIRouter(prefix="/purge", tags=["purge"])


@router.post("")
def purge_data(
    _user_id: int = Depends(get_current_user_id),
    db: Session = Depends(get_db),
):
    """Delete all projects, meetings, transcripts, minutes, speakers, templates, and uploaded files. Requires auth."""
    return purge_all_data(db, settings)
