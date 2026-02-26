"""Transcription service using Whisper v3 Turbo."""
import logging
from pathlib import Path

from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.database import SessionLocal
from app.models import Meeting, MeetingStatus, Transcript

logger = logging.getLogger(__name__)


def transcribe_audio(audio_path: str) -> tuple[str, str | None, float | None]:
    """
    Transcribe audio file using Whisper v3 Turbo.
    Returns (raw_text, language, duration_seconds).
    """
    from whisper_turbo import MLXWhisperTranscriber

    transcriber = MLXWhisperTranscriber(model_name=settings.whisper_model)
    text, segments = transcriber.transcribe_file(audio_path)

    # Infer duration from segments if available
    duration = None
    if segments:
        last = max(s.get("end", 0) for s in segments)
        duration = last

    # Language may be in segments metadata; fallback to None
    lang = None
    return (text or "", lang, duration)


def transcribe_meeting_sync(meeting_id: int) -> None:
    """Synchronously transcribe a meeting and save to DB."""
    db = SessionLocal()
    try:
        meeting = db.query(Meeting).filter(Meeting.id == meeting_id).first()
        if not meeting or not meeting.audio_path:
            logger.warning("Meeting %s not found or no audio", meeting_id)
            return

        path = Path(meeting.audio_path)
        if not path.exists():
            meeting.status = MeetingStatus.ERROR
            meeting.error_message = f"Audio file not found: {path}"
            db.commit()
            return

        try:
            raw_text, lang, duration = transcribe_audio(str(path))

            transcript = Transcript(
                meeting_id=meeting_id,
                raw_text=raw_text,
                language=lang,
                duration_seconds=duration,
            )
            db.add(transcript)

            meeting.status = MeetingStatus.FORMATTING
            db.commit()

            # Trigger LLM formatting (will be wired in Phase 3)
            from app.services.formatting import format_meeting_sync
            format_meeting_sync(meeting_id)

        except Exception as e:
            logger.exception("Transcription failed for meeting %s", meeting_id)
            meeting.status = MeetingStatus.ERROR
            meeting.error_message = str(e)[:1024]
            db.commit()
    finally:
        db.close()


def transcribe_meeting_async(meeting_id: int) -> None:
    """Trigger transcription in background."""
    import threading
    t = threading.Thread(target=transcribe_meeting_sync, args=(meeting_id,))
    t.daemon = True
    t.start()
