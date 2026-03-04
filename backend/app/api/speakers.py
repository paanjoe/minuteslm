"""Speakers API - voice samples for 'who is this guy' (future diarization)."""
from pathlib import Path
from typing import List

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile

from app.core.auth import get_current_user_id
from app.core.config import settings
from app.core.database import get_db
from app.models import Speaker
from app.schemas.speaker import SpeakerCreate, SpeakerResponse
from sqlalchemy.orm import Session

router = APIRouter(prefix="/speakers", tags=["speakers"])


@router.get("", response_model=List[SpeakerResponse])
def list_speakers(
    user_id: int = Depends(get_current_user_id),
    db: Session = Depends(get_db),
):
    """List all speaker profiles for the current user."""
    return (
        db.query(Speaker)
        .filter(Speaker.user_id == user_id)
        .order_by(Speaker.created_at.desc())
        .all()
    )


@router.post("", response_model=SpeakerResponse)
def create_speaker(
    payload: SpeakerCreate,
    user_id: int = Depends(get_current_user_id),
    db: Session = Depends(get_db),
):
    """Create a speaker profile (no sample yet)."""
    speaker = Speaker(user_id=user_id, name=payload.name)
    db.add(speaker)
    db.commit()
    db.refresh(speaker)
    return speaker


@router.post("/with-sample", response_model=SpeakerResponse)
async def create_speaker_with_sample(
    name: str = Form(...),
    file: UploadFile = File(...),
    user_id: int = Depends(get_current_user_id),
    db: Session = Depends(get_db),
):
    """Create a new speaker and attach a voice sample in one step (e.g. after 'who is this?')."""
    speaker = Speaker(user_id=user_id, name=name.strip() or "Unknown")
    db.add(speaker)
    db.commit()
    db.refresh(speaker)

    ext = Path(file.filename or "").suffix.lower()
    if ext not in (".wav", ".mp3", ".m4a", ".webm", ".ogg"):
        db.delete(speaker)
        db.commit()
        raise HTTPException(
            status_code=400,
            detail="Invalid format. Use wav, mp3, m4a, webm, or ogg.",
        )
    upload_dir = Path(settings.speaker_samples_dir)
    upload_dir.mkdir(parents=True, exist_ok=True)
    safe_name = f"{user_id}_{speaker.id}_{Path(file.filename or 'sample').name}"
    path = upload_dir / safe_name
    contents = await file.read()
    if len(contents) > 10 * 1024 * 1024:
        db.delete(speaker)
        db.commit()
        raise HTTPException(status_code=400, detail="File too large. Max 10MB.")
    path.write_bytes(contents)
    speaker.audio_path = str(path)
    db.commit()
    db.refresh(speaker)
    return speaker


@router.post("/{speaker_id}/sample", response_model=SpeakerResponse)
async def upload_sample(
    speaker_id: int,
    file: UploadFile = File(...),
    user_id: int = Depends(get_current_user_id),
    db: Session = Depends(get_db),
):
    """Upload a voice sample for this speaker."""
    speaker = (
        db.query(Speaker)
        .filter(Speaker.id == speaker_id, Speaker.user_id == user_id)
        .first()
    )
    if not speaker:
        raise HTTPException(status_code=404, detail="Speaker not found")

    ext = Path(file.filename or "").suffix.lower()
    if ext not in (".wav", ".mp3", ".m4a", ".webm", ".ogg"):
        raise HTTPException(
            status_code=400,
            detail="Invalid format. Use wav, mp3, m4a, webm, or ogg.",
        )

    upload_dir = Path(settings.speaker_samples_dir)
    upload_dir.mkdir(parents=True, exist_ok=True)
    safe_name = f"{user_id}_{speaker_id}_{Path(file.filename or 'sample').name}"
    path = upload_dir / safe_name

    contents = await file.read()
    if len(contents) > 10 * 1024 * 1024:  # 10 MB max for samples
        raise HTTPException(status_code=400, detail="File too large. Max 10MB.")
    path.write_bytes(contents)

    speaker.audio_path = str(path)
    db.commit()
    db.refresh(speaker)
    return speaker


@router.delete("/{speaker_id}")
def delete_speaker(
    speaker_id: int,
    user_id: int = Depends(get_current_user_id),
    db: Session = Depends(get_db),
):
    """Delete a speaker profile and their sample file."""
    speaker = (
        db.query(Speaker)
        .filter(Speaker.id == speaker_id, Speaker.user_id == user_id)
        .first()
    )
    if not speaker:
        raise HTTPException(status_code=404, detail="Speaker not found")
    if speaker.audio_path:
        p = Path(speaker.audio_path)
        if p.exists():
            p.unlink(missing_ok=True)
    db.delete(speaker)
    db.commit()
    return {"ok": True}
