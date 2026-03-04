"""Transcription service using Whisper v3 Turbo."""
import logging
from pathlib import Path

from app.core.config import settings
from app.core.database import SessionLocal
from app.models import Meeting, MeetingStatus, Transcript
from app.services.progress import clear_progress, set_progress
from app.services.snippet_extract import extract_and_save_snippets

logger = logging.getLogger(__name__)


def transcribe_audio(audio_path: str) -> tuple[str, str | None, float | None, list]:
    """
    Transcribe audio file using Whisper v3 Turbo.
    Returns (raw_text, language, duration_seconds, segments).
    segments are list of dicts with start/end (seconds) for snippet extraction.
    """
    from whisper_turbo import MLXWhisperTranscriber

    transcriber = MLXWhisperTranscriber(
        model_name=settings.whisper_model,
        api_enabled=False,  # We save to DB ourselves, don't post to external API
    )
    text, segments = transcriber.transcribe_file(audio_path)
    segments = segments or []

    # Infer duration from segments if available (convert to native float for PostgreSQL)
    duration = None
    if segments:
        last = max(s.get("end", 0) for s in segments)
        duration = float(last)

    # Language may be in segments metadata; fallback to None
    lang = None
    return (text or "", lang, duration, segments)


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
            clear_progress(meeting_id)
            db.commit()
            return

        try:
            set_progress(meeting_id, "Loading Whisper model and transcribing...")
            raw_text, lang, duration, segments = transcribe_audio(str(path))
            set_progress(meeting_id, "Detecting speakers and extracting snippets...")
            try:
                extract_and_save_snippets(meeting_id, str(path), segments)
            except Exception as e:
                logger.warning("Speaker snippet extraction failed (non-fatal): %s", e)
            set_progress(meeting_id, "Transcription done. Formatting with LLM...")

            transcript = Transcript(
                meeting_id=meeting_id,
                raw_text=raw_text,
                language=lang,
                duration_seconds=float(duration) if duration is not None else None,
            )
            db.add(transcript)

            meeting.status = MeetingStatus.FORMATTING
            db.commit()

            from app.services.formatting import format_meeting_sync
            format_meeting_sync(meeting_id)
            clear_progress(meeting_id)

        except Exception as e:
            logger.exception("Transcription failed for meeting %s", meeting_id)
            meeting.status = MeetingStatus.ERROR
            meeting.error_message = str(e)[:1024]
            clear_progress(meeting_id)
            db.commit()
    finally:
        db.close()


def transcribe_meeting_async(meeting_id: int) -> None:
    """Trigger transcription in background."""
    import threading
    t = threading.Thread(target=transcribe_meeting_sync, args=(meeting_id,))
    t.daemon = True
    t.start()
