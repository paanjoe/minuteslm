"""Meeting API routes."""
from pathlib import Path
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Query
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session

from app.core.auth import get_current_user_id
from app.core.config import settings
from app.core.database import get_db
from app.models import Meeting, MeetingStatus, Project, Template, Transcript, Minute, ActionItem, MeetingSpeakerSnippet, Speaker
from app.services.progress import get_progress, set_progress
from app.schemas import (
    MeetingCreate,
    MeetingResponse,
    MeetingListResponse,
    MeetingUpdate,
    TranscriptResponse,
    MinuteResponse,
    ActionItemResponse,
)
from app.schemas.meeting_speaker_snippet import MeetingSpeakerSnippetResponse, IdentifySpeakerRequest

router = APIRouter(prefix="/meetings", tags=["meetings"])


def _get_meeting_owned(
    meeting_id: int, user_id: int, db: Session
) -> Meeting:
    """Return meeting if it belongs to user via project; else 404."""
    meeting = (
        db.query(Meeting)
        .join(Project, Meeting.project_id == Project.id)
        .filter(Meeting.id == meeting_id, Project.user_id == user_id)
        .first()
    )
    if not meeting:
        raise HTTPException(status_code=404, detail="Meeting not found")
    return meeting


@router.get("", response_model=List[MeetingListResponse])
def list_meetings(
    project_id: int = Query(..., description="Filter by project"),
    skip: int = 0,
    limit: int = 50,
    user_id: int = Depends(get_current_user_id),
    db: Session = Depends(get_db),
):
    """List meetings in a project."""
    project = (
        db.query(Project)
        .filter(Project.id == project_id, Project.user_id == user_id)
        .first()
    )
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    meetings = (
        db.query(Meeting)
        .filter(Meeting.project_id == project_id)
        .order_by(Meeting.created_at.desc())
        .offset(skip)
        .limit(limit)
        .all()
    )
    return meetings


@router.post("", response_model=MeetingResponse)
def create_meeting(
    payload: MeetingCreate,
    user_id: int = Depends(get_current_user_id),
    db: Session = Depends(get_db),
):
    """Create a new meeting in a project."""
    project = (
        db.query(Project)
        .filter(Project.id == payload.project_id, Project.user_id == user_id)
        .first()
    )
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    meeting = Meeting(project_id=payload.project_id, title=payload.title)
    db.add(meeting)
    db.commit()
    db.refresh(meeting)
    return meeting


@router.get("/{meeting_id}", response_model=MeetingResponse)
def get_meeting(
    meeting_id: int,
    user_id: int = Depends(get_current_user_id),
    db: Session = Depends(get_db),
):
    """Get a single meeting."""
    meeting = _get_meeting_owned(meeting_id, user_id, db)
    resp = MeetingResponse.model_validate(meeting)
    if meeting.status in (MeetingStatus.TRANSCRIBING, MeetingStatus.FORMATTING):
        if msg := get_progress(meeting_id):
            resp = resp.model_copy(update={"progress_message": msg})
    return resp


@router.patch("/{meeting_id}", response_model=MeetingResponse)
def update_meeting(
    meeting_id: int,
    payload: MeetingUpdate,
    user_id: int = Depends(get_current_user_id),
    db: Session = Depends(get_db),
):
    """Update meeting (title and/or minutes template override)."""
    meeting = _get_meeting_owned(meeting_id, user_id, db)
    if payload.title is not None:
        meeting.title = payload.title
    if payload.template_id is not None:
        if payload.template_id:
            t = (
                db.query(Template)
                .filter(Template.id == payload.template_id, Template.user_id == user_id)
                .first()
            )
            if not t:
                raise HTTPException(status_code=404, detail="Template not found")
        meeting.template_id = payload.template_id if payload.template_id else None
    db.commit()
    db.refresh(meeting)
    return MeetingResponse.model_validate(meeting)


@router.post("/{meeting_id}/upload", response_model=MeetingResponse)
async def upload_audio(
    meeting_id: int,
    file: UploadFile = File(...),
    user_id: int = Depends(get_current_user_id),
    db: Session = Depends(get_db),
):
    """Upload audio file for a meeting and trigger transcription."""
    meeting = _get_meeting_owned(meeting_id, user_id, db)

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

    set_progress(meeting_id, "Starting transcription...")
    from app.services.transcription import transcribe_meeting_async
    transcribe_meeting_async(meeting_id)

    resp = MeetingResponse.model_validate(meeting)
    return resp.model_copy(update={"progress_message": "Starting transcription..."})


@router.get("/{meeting_id}/transcript", response_model=Optional[TranscriptResponse])
def get_transcript(
    meeting_id: int,
    user_id: int = Depends(get_current_user_id),
    db: Session = Depends(get_db),
):
    """Get transcript for a meeting."""
    _get_meeting_owned(meeting_id, user_id, db)
    transcript = (
        db.query(Transcript)
        .filter(Transcript.meeting_id == meeting_id)
        .first()
    )
    return transcript


@router.get("/{meeting_id}/minutes", response_model=Optional[MinuteResponse])
def get_minutes(
    meeting_id: int,
    user_id: int = Depends(get_current_user_id),
    db: Session = Depends(get_db),
):
    """Get formatted minutes for a meeting."""
    _get_meeting_owned(meeting_id, user_id, db)
    minute = (
        db.query(Minute)
        .filter(Minute.meeting_id == meeting_id)
        .first()
    )
    return minute


@router.get("/{meeting_id}/action-items", response_model=List[ActionItemResponse])
def get_action_items(
    meeting_id: int,
    user_id: int = Depends(get_current_user_id),
    db: Session = Depends(get_db),
):
    """Get action items for a meeting."""
    _get_meeting_owned(meeting_id, user_id, db)
    items = (
        db.query(ActionItem)
        .filter(ActionItem.meeting_id == meeting_id)
        .all()
    )
    return items


@router.get("/{meeting_id}/detected-speakers", response_model=List[MeetingSpeakerSnippetResponse])
def list_detected_speakers(
    meeting_id: int,
    user_id: int = Depends(get_current_user_id),
    db: Session = Depends(get_db),
):
    """List detected (unknown) speaker snippets for this meeting. User can play and identify later."""
    _get_meeting_owned(meeting_id, user_id, db)
    snippets = (
        db.query(MeetingSpeakerSnippet)
        .filter(MeetingSpeakerSnippet.meeting_id == meeting_id)
        .order_by(MeetingSpeakerSnippet.start_sec.asc().nullslast(), MeetingSpeakerSnippet.id.asc())
        .all()
    )
    return snippets


@router.get("/{meeting_id}/detected-speakers/{snippet_id}/audio")
def get_detected_speaker_audio(
    meeting_id: int,
    snippet_id: int,
    user_id: int = Depends(get_current_user_id),
    db: Session = Depends(get_db),
):
    """Stream the audio snippet for playback (e.g. to identify who spoke)."""
    _get_meeting_owned(meeting_id, user_id, db)
    snippet = (
        db.query(MeetingSpeakerSnippet)
        .filter(
            MeetingSpeakerSnippet.id == snippet_id,
            MeetingSpeakerSnippet.meeting_id == meeting_id,
        )
        .first()
    )
    if not snippet:
        raise HTTPException(status_code=404, detail="Snippet not found")
    path = Path(snippet.snippet_path)
    if not path.exists():
        raise HTTPException(status_code=404, detail="Audio file not found")
    return FileResponse(path, media_type="audio/wav")


@router.patch("/{meeting_id}/detected-speakers/{snippet_id}/identify", response_model=MeetingSpeakerSnippetResponse)
def identify_detected_speaker(
    meeting_id: int,
    snippet_id: int,
    payload: IdentifySpeakerRequest,
    user_id: int = Depends(get_current_user_id),
    db: Session = Depends(get_db),
):
    """Link this snippet to an existing speaker (speaker_id) or create a new speaker (name) and link."""
    _get_meeting_owned(meeting_id, user_id, db)
    snippet = (
        db.query(MeetingSpeakerSnippet)
        .filter(
            MeetingSpeakerSnippet.id == snippet_id,
            MeetingSpeakerSnippet.meeting_id == meeting_id,
        )
        .first()
    )
    if not snippet:
        raise HTTPException(status_code=404, detail="Snippet not found")
    if payload.speaker_id is not None:
        speaker = db.query(Speaker).filter(Speaker.id == payload.speaker_id, Speaker.user_id == user_id).first()
        if not speaker:
            raise HTTPException(status_code=404, detail="Speaker not found")
        snippet.speaker_id = payload.speaker_id
    elif payload.name and payload.name.strip():
        speaker = Speaker(user_id=user_id, name=payload.name.strip(), audio_path=snippet.snippet_path)
        db.add(speaker)
        db.flush()
        snippet.speaker_id = speaker.id
    else:
        raise HTTPException(status_code=400, detail="Provide speaker_id or name")
    db.commit()
    db.refresh(snippet)
    return snippet


@router.delete("/{meeting_id}")
def delete_meeting(
    meeting_id: int,
    user_id: int = Depends(get_current_user_id),
    db: Session = Depends(get_db),
):
    """Delete a meeting and its transcript, minutes, action items, and audio file."""
    meeting = _get_meeting_owned(meeting_id, user_id, db)

    # Delete audio file if it exists
    if meeting.audio_path:
        path = Path(meeting.audio_path)
        if path.exists():
            path.unlink(missing_ok=True)

    db.delete(meeting)
    db.commit()
    return {"ok": True}


@router.post("/{meeting_id}/retranscribe", response_model=MeetingResponse)
def retranscribe(
    meeting_id: int,
    user_id: int = Depends(get_current_user_id),
    db: Session = Depends(get_db),
):
    """Re-run transcription on existing audio. Requires audio to be uploaded."""
    meeting = _get_meeting_owned(meeting_id, user_id, db)
    if not meeting.audio_path:
        raise HTTPException(
            status_code=400, detail="No audio file. Upload audio first."
        )
    path = Path(meeting.audio_path)
    if not path.exists():
        raise HTTPException(status_code=400, detail="Audio file not found")

    # Delete existing transcript, minutes, and detected speaker snippets (will be re-created)
    db.query(Transcript).filter(Transcript.meeting_id == meeting_id).delete()
    db.query(Minute).filter(Minute.meeting_id == meeting_id).delete()
    db.query(MeetingSpeakerSnippet).filter(MeetingSpeakerSnippet.meeting_id == meeting_id).delete()
    meeting.status = MeetingStatus.TRANSCRIBING
    meeting.error_message = None
    db.commit()

    set_progress(meeting_id, "Starting re-transcription...")
    from app.services.transcription import transcribe_meeting_async
    transcribe_meeting_async(meeting_id)

    db.refresh(meeting)
    resp = MeetingResponse.model_validate(meeting)
    return resp.model_copy(update={"progress_message": "Starting re-transcription..."})


@router.post("/{meeting_id}/reformat", response_model=MeetingResponse)
def reformat(
    meeting_id: int,
    user_id: int = Depends(get_current_user_id),
    db: Session = Depends(get_db),
):
    """Re-run LLM formatting on existing transcript. Requires transcript to exist."""
    meeting = _get_meeting_owned(meeting_id, user_id, db)

    transcript = (
        db.query(Transcript)
        .filter(Transcript.meeting_id == meeting_id)
        .first()
    )
    if not transcript:
        raise HTTPException(
            status_code=400, detail="No transcript. Transcribe audio first."
        )

    # Delete existing minutes
    db.query(Minute).filter(Minute.meeting_id == meeting_id).delete()
    meeting.status = MeetingStatus.FORMATTING
    meeting.error_message = None
    db.commit()

    set_progress(meeting_id, "Re-formatting with Ollama...")
    from app.services.formatting import format_meeting_sync
    format_meeting_sync(meeting_id)  # Run synchronously so response includes final state

    db.refresh(meeting)
    resp = MeetingResponse.model_validate(meeting)
    if meeting.status in (MeetingStatus.TRANSCRIBING, MeetingStatus.FORMATTING):
        if msg := get_progress(meeting_id):
            resp = resp.model_copy(update={"progress_message": msg})
    return resp
