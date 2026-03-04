"""
Extract audio snippets from meeting for detected "speakers" (turns).
Uses Whisper segments: group by pause into turns, extract one snippet per turn for user to review and identify.
"""
import logging
from pathlib import Path
from typing import Any

from app.core.config import settings
from app.core.database import SessionLocal
from app.models import MeetingSpeakerSnippet

logger = logging.getLogger(__name__)

# Max gap (sec) between segments to consider same "turn"
TURN_GAP_SEC = 2.0
# Min duration (sec) for a turn to become a snippet
MIN_TURN_SEC = 1.5
# Max snippets to create per meeting (first N turns)
MAX_SNIPPETS = 12


def _segments_to_turns(segments: list[dict[str, Any]]) -> list[tuple[float, float]]:
    """Group segments into turns by gap. Returns list of (start_sec, end_sec)."""
    if not segments:
        return []
    sorted_segs = sorted(
        (float(s.get("start", 0)), float(s.get("end", 0)))
        for s in segments
        if isinstance(s.get("start"), (int, float)) and isinstance(s.get("end"), (int, float))
    )
    if not sorted_segs:
        return []
    turns: list[tuple[float, float]] = []
    turn_start, turn_end = sorted_segs[0]
    for start, end in sorted_segs[1:]:
        if start - turn_end <= TURN_GAP_SEC:
            turn_end = end
        else:
            if turn_end - turn_start >= MIN_TURN_SEC:
                turns.append((turn_start, turn_end))
            turn_start, turn_end = start, end
    if turn_end - turn_start >= MIN_TURN_SEC:
        turns.append((turn_start, turn_end))
    return turns[:MAX_SNIPPETS]


def _extract_snippet_audio(
    audio_path: str, start_sec: float, end_sec: float, out_path: Path
) -> bool:
    """Extract segment to WAV using pydub. Returns True on success."""
    try:
        from pydub import AudioSegment
    except ImportError:
        logger.warning("pydub not installed, skipping snippet extraction")
        return False
    path = Path(audio_path)
    if not path.exists():
        return False
    start_ms = int(start_sec * 1000)
    end_ms = int(end_sec * 1000)
    if end_ms <= start_ms:
        return False
    try:
        # pydub can load wav, mp3, m4a, etc.
        audio = AudioSegment.from_file(str(path))
        if end_ms > len(audio):
            end_ms = len(audio)
        if start_ms >= len(audio):
            return False
        segment = audio[start_ms:end_ms]
        out_path.parent.mkdir(parents=True, exist_ok=True)
        segment.export(str(out_path), format="wav")
        return True
    except Exception as e:
        logger.warning("Failed to extract snippet %s: %s", out_path, e)
        return False


def extract_and_save_snippets(
    meeting_id: int, audio_path: str, segments: list[dict[str, Any]]
) -> int:
    """
    From Whisper segments, build turns, extract one WAV snippet per turn,
    save to uploads/detected_speakers and create MeetingSpeakerSnippet rows.
    Returns number of snippets created.
    """
    turns = _segments_to_turns(segments)
    if not turns:
        return 0
    out_dir = Path(settings.detected_snippets_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    db = SessionLocal()
    created = 0
    try:
        for i, (start_sec, end_sec) in enumerate(turns):
            out_path = out_dir / f"meeting_{meeting_id}_snippet_{i + 1}.wav"
            if not _extract_snippet_audio(audio_path, start_sec, end_sec, out_path):
                continue
            snippet = MeetingSpeakerSnippet(
                meeting_id=meeting_id,
                snippet_path=str(out_path),
                label=f"Speaker {i + 1}",
                start_sec=start_sec,
                end_sec=end_sec,
            )
            db.add(snippet)
            created += 1
        db.commit()
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()
    if created:
        logger.info("Created %d speaker snippets for meeting %s", created, meeting_id)
    return created
