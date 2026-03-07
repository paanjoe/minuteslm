"""Meeting API routes."""
from pathlib import Path
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Query
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session

from app.core.auth import get_current_user_id
from app.core.config import settings
from app.core.database import get_db
from app.models import (
    Meeting,
    MeetingStatus,
    Project,
    Template,
    Transcript,
    Minute,
    ActionItem,
    MeetingSpeakerSnippet,
    Speaker,
)
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


def _ensure_speaker_profiles_for_names(
    user_id: int,
    attendee: Optional[str],
    absentees: Optional[str],
    db: Session,
) -> None:
    """Create Speaker profiles for any attendee/absentee names that don't exist yet (so they appear on Voice samples)."""
    names = set()
    for raw in (attendee or "", absentees or ""):
        for line in raw.split("\n"):
            name = line.strip()
            if name:
                names.add(name)
    for name in names:
        existing = (
            db.query(Speaker)
            .filter(Speaker.user_id == user_id, Speaker.name == name)
            .first()
        )
        if not existing:
            db.add(Speaker(user_id=user_id, name=name))


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
    _ensure_speaker_profiles_for_names(
        user_id, payload.attendee, payload.absentees, db
    )
    meeting = Meeting(
        project_id=payload.project_id,
        title=payload.title,
        discussion_date_time=payload.discussion_date_time,
        attendee=payload.attendee,
        absentees=payload.absentees,
        minutes_taken_by=payload.minutes_taken_by,
        summary_context=payload.summary_context,
    )
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
        msg, pct = get_progress(meeting_id)
        if msg is not None:
            resp = resp.model_copy(
                update={"progress_message": msg, "progress_percentage": pct}
            )
    return resp


@router.patch("/{meeting_id}", response_model=MeetingResponse)
def update_meeting(
    meeting_id: int,
    payload: MeetingUpdate,
    user_id: int = Depends(get_current_user_id),
    db: Session = Depends(get_db),
):
    """Update meeting (title, template, and/or metadata)."""
    meeting = _get_meeting_owned(meeting_id, user_id, db)
    if payload.title is not None:
        meeting.title = payload.title
    if payload.discussion_date_time is not None:
        meeting.discussion_date_time = payload.discussion_date_time
    if payload.attendee is not None:
        meeting.attendee = payload.attendee
    if payload.absentees is not None:
        meeting.absentees = payload.absentees
    if payload.minutes_taken_by is not None:
        meeting.minutes_taken_by = payload.minutes_taken_by
    if payload.attendee is not None or payload.absentees is not None:
        _ensure_speaker_profiles_for_names(
            user_id,
            payload.attendee if payload.attendee is not None else meeting.attendee,
            payload.absentees if payload.absentees is not None else meeting.absentees,
            db,
        )
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
    if payload.summary_context is not None:
        meeting.summary_context = payload.summary_context
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
    meeting.status = MeetingStatus.RECORDING
    db.commit()
    db.refresh(meeting)

    resp = MeetingResponse.model_validate(meeting)
    return resp


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


@router.post("/{meeting_id}/transcribe", response_model=MeetingResponse)
def start_transcribe(
    meeting_id: int,
    user_id: int = Depends(get_current_user_id),
    db: Session = Depends(get_db),
):
    """Start transcription (after upload). Requires audio; does not delete existing transcript."""
    meeting = _get_meeting_owned(meeting_id, user_id, db)
    if not meeting.audio_path:
        raise HTTPException(
            status_code=400, detail="No audio file. Upload audio first."
        )
    path = Path(meeting.audio_path)
    if not path.exists():
        raise HTTPException(status_code=400, detail="Audio file not found")
    meeting.status = MeetingStatus.TRANSCRIBING
    meeting.error_message = None
    db.commit()
    set_progress(meeting_id, "Starting transcription...", 0)
    from app.services.transcription import transcribe_meeting_async
    transcribe_meeting_async(meeting_id)
    db.refresh(meeting)
    resp = MeetingResponse.model_validate(meeting)
    return resp.model_copy(
        update={"progress_message": "Starting transcription...", "progress_percentage": 0}
    )


@router.post("/{meeting_id}/retranscribe", response_model=MeetingResponse)
def retranscribe(
    meeting_id: int,
    user_id: int = Depends(get_current_user_id),
    db: Session = Depends(get_db),
):
    """Re-run transcription on existing audio (deletes current transcript and minutes)."""
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

    set_progress(meeting_id, "Starting re-transcription...", 0)
    from app.services.transcription import transcribe_meeting_async
    transcribe_meeting_async(meeting_id)

    db.refresh(meeting)
    resp = MeetingResponse.model_validate(meeting)
    return resp.model_copy(
        update={"progress_message": "Starting re-transcription...", "progress_percentage": 0}
    )


@router.get("/{meeting_id}/format-prompt-preview")
def get_format_prompt_preview(
    meeting_id: int,
    user_id: int = Depends(get_current_user_id),
    db: Session = Depends(get_db),
):
    """Return the exact prompt that would be sent to Qwen/Ollama for this meeting (for debugging format not being followed)."""
    _get_meeting_owned(meeting_id, user_id, db)
    transcript = (
        db.query(Transcript)
        .filter(Transcript.meeting_id == meeting_id)
        .first()
    )
    if not transcript:
        raise HTTPException(status_code=400, detail="No transcript. Transcribe first.")
    from app.services.formatting import build_format_prompt, _resolve_template_for_meeting
    meeting = db.query(Meeting).filter(Meeting.id == meeting_id).first()
    template = _resolve_template_for_meeting(meeting, db)
    prompt_suffix = template.prompt_suffix if template else None
    template_sample = template.sample_content if template else None
    format_spec_markdown = getattr(template, "format_spec_markdown", None) if template else None
    summary_context = getattr(meeting, "summary_context", None) or None
    prompt = build_format_prompt(
        transcript.raw_text,
        prompt_suffix=prompt_suffix,
        template_sample=template_sample,
        format_spec_markdown=format_spec_markdown,
        transcript_max_chars=4000,
        summary_context=summary_context,
    )
    return {"prompt": prompt, "model": settings.ollama_model}


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

    set_progress(meeting_id, "Re-formatting with Ollama...", 85)
    from app.services.formatting import format_meeting_sync
    format_meeting_sync(meeting_id)  # Run synchronously so response includes final state

    db.refresh(meeting)
    resp = MeetingResponse.model_validate(meeting)
    if meeting.status in (MeetingStatus.TRANSCRIBING, MeetingStatus.FORMATTING):
        msg, pct = get_progress(meeting_id)
        if msg is not None:
            resp = resp.model_copy(
                update={"progress_message": msg, "progress_percentage": pct}
            )
    return resp
