"""Transcription service using Whisper v3 Turbo. Supports long audio via chunking (channeling)."""
import logging
import os
from pathlib import Path
from typing import Any

from app.core.config import settings
from app.core.database import SessionLocal
from app.models import Meeting, MeetingStatus, Transcript
from app.services.long_audio import (
    get_audio_duration_sec,
    merge_chunk_segments,
    normalize_segments,
    split_audio_into_chunk_paths,
)
from app.services.progress import clear_progress, set_progress
from app.services.snippet_extract import extract_and_save_snippets

logger = logging.getLogger(__name__)


def transcribe_audio(audio_path: str) -> tuple[str, str | None, float | None, list[dict[str, Any]]]:
    """
    Transcribe audio file using Whisper v3 Turbo.
    Returns (raw_text, language, duration_seconds, segments).
    segments are list of dicts with start/end/text for snippet extraction and timestamped display.
    """
    from whisper_turbo import MLXWhisperTranscriber

    transcriber = MLXWhisperTranscriber(
        model_name=settings.whisper_model,
        api_enabled=False,
    )
    text, segments = transcriber.transcribe_file(audio_path)
    segments = segments or []

    duration = None
    if segments:
        last = max(s.get("end", 0) for s in segments)
        duration = float(last)

    lang = None
    normalized = normalize_segments(segments)
    return (text or "", lang, duration, normalized)


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
            chunk_sec = getattr(settings, "transcription_chunk_duration_sec", 600)
            audio_path_str = str(path)
            duration_sec = get_audio_duration_sec(audio_path_str)
            raw_text = ""
            lang = None
            duration: float | None = None
            segments: list[dict[str, Any]] = []

            if duration_sec > chunk_sec and duration_sec > 0:
                set_progress(meeting_id, "Splitting audio into segments...", 5)
                chunk_paths = split_audio_into_chunk_paths(audio_path_str, chunk_sec)
                if not chunk_paths:
                    set_progress(meeting_id, "Loading Whisper model and transcribing...", 15)
                    raw_text, lang, duration, segments = transcribe_audio(audio_path_str)
                else:
                    chunk_results: list[tuple[list[dict[str, Any]], str, float]] = []
                    total = len(chunk_paths)
                    for idx, (chunk_path, offset_sec) in enumerate(chunk_paths):
                        # 10% to 65% for transcription chunks
                        pct = 10 + int(55 * (idx + 1) / total) if total else 10
                        set_progress(
                            meeting_id,
                            "Transcribing segment %d of %d..." % (idx + 1, total),
                            pct,
                        )
                        try:
                            c_text, c_lang, c_dur, c_segs = transcribe_audio(chunk_path)
                            if c_lang:
                                lang = c_lang
                            chunk_results.append((c_segs, c_text, offset_sec))
                        finally:
                            try:
                                os.unlink(chunk_path)
                            except OSError:
                                pass
                    segments, raw_text = merge_chunk_segments(chunk_results)
                    duration = duration_sec
                    logger.info("Long audio: merged %d segments from %d chunks", len(segments), total)
            else:
                set_progress(meeting_id, "Loading Whisper model and transcribing...", 15)
                raw_text, lang, duration, segments = transcribe_audio(audio_path_str)

            set_progress(meeting_id, "Detecting speakers and extracting snippets...", 70)
            try:
                extract_and_save_snippets(meeting_id, audio_path_str, segments)
            except Exception as e:
                logger.warning("Speaker snippet extraction failed (non-fatal): %s", e)
            set_progress(meeting_id, "Transcription complete. Formatting with LLM...", 80)

            transcript = Transcript(
                meeting_id=meeting_id,
                raw_text=raw_text,
                language=lang,
                duration_seconds=float(duration) if duration is not None else None,
                segments=segments if segments else None,
            )
            db.add(transcript)

            meeting.status = MeetingStatus.TRANSCRIBED
            db.commit()
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
