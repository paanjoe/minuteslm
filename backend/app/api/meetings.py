"""Meeting API routes."""
from pathlib import Path
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.database import get_db
from app.models import Meeting, MeetingStatus, Transcript, Minute, ActionItem
from app.schemas import (
    MeetingCreate,
    MeetingResponse,
    MeetingListResponse,
    TranscriptResponse,
    MinuteResponse,
    ActionItemResponse,
)

router = APIRouter(prefix="/meetings", tags=["meetings"])


@router.get("", response_model=List[MeetingListResponse])
def list_meetings(
    skip: int = 0,
    limit: int = 50,
    db: Session = Depends(get_db),
):
    """List all meetings."""
    meetings = (
        db.query(Meeting)
        .order_by(Meeting.created_at.desc())
        .offset(skip)
        .limit(limit)
        .all()
    )
    return meetings


@router.post("", response_model=MeetingResponse)
def create_meeting(
    payload: MeetingCreate,
    db: Session = Depends(get_db),
):
    """Create a new meeting record."""
    meeting = Meeting(title=payload.title)
    db.add(meeting)
    db.commit()
    db.refresh(meeting)
    return meeting


@router.get("/{meeting_id}", response_model=MeetingResponse)
def get_meeting(
    meeting_id: int,
    db: Session = Depends(get_db),
):
    """Get a single meeting."""
    meeting = db.query(Meeting).filter(Meeting.id == meeting_id).first()
    if not meeting:
        raise HTTPException(status_code=404, detail="Meeting not found")
    return meeting


@router.post("/{meeting_id}/upload", response_model=MeetingResponse)
async def upload_audio(
    meeting_id: int,
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
):
    """Upload audio file for a meeting and trigger transcription."""
    meeting = db.query(Meeting).filter(Meeting.id == meeting_id).first()
    if not meeting:
        raise HTTPException(status_code=404, detail="Meeting not found")

    # Validate file type
    ext = Path(file.filename or "").suffix.lower()
    if ext not in (".wav", ".mp3", ".m4a", ".webm"):
        raise HTTPException(
            status_code=400,
            detail="Invalid format. Use wav, mp3, m4a, or webm.",
        )

    # Ensure upload dir exists
    upload_dir = Path(settings.audio_upload_dir)
    upload_dir.mkdir(parents=True, exist_ok=True)

    # Save file
    safe_name = f"{meeting_id}_{Path(file.filename or 'audio').name}"
    path = upload_dir / safe_name

    contents = await file.read()
    if len(contents) > settings.max_upload_mb * 1024 * 1024:
        raise HTTPException(
            status_code=400,
            detail=f"File too large. Max {settings.max_upload_mb}MB.",
        )

    path.write_bytes(contents)

    meeting.audio_path = str(path)
    meeting.status = MeetingStatus.TRANSCRIBING
    db.commit()
    db.refresh(meeting)

    # Trigger transcription in background (will be wired in Phase 2)
    from app.services.transcription import transcribe_meeting_async
    transcribe_meeting_async(meeting_id)

    return meeting


@router.get("/{meeting_id}/transcript", response_model=Optional[TranscriptResponse])
def get_transcript(
    meeting_id: int,
    db: Session = Depends(get_db),
):
    """Get transcript for a meeting."""
    transcript = (
        db.query(Transcript)
        .filter(Transcript.meeting_id == meeting_id)
        .first()
    )
    return transcript


@router.get("/{meeting_id}/minutes", response_model=Optional[MinuteResponse])
def get_minutes(
    meeting_id: int,
    db: Session = Depends(get_db),
):
    """Get formatted minutes for a meeting."""
    minute = (
        db.query(Minute)
        .filter(Minute.meeting_id == meeting_id)
        .first()
    )
    return minute


@router.get("/{meeting_id}/action-items", response_model=List[ActionItemResponse])
def get_action_items(
    meeting_id: int,
    db: Session = Depends(get_db),
):
    """Get action items for a meeting."""
    items = (
        db.query(ActionItem)
        .filter(ActionItem.meeting_id == meeting_id)
        .all()
    )
    return items
