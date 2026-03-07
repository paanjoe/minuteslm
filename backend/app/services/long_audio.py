"""Split long audio into chunks for transcription (channeling) and merge segment results."""
import logging
import tempfile
from pathlib import Path
from typing import Any

from app.core.config import settings

logger = logging.getLogger(__name__)


def get_audio_duration_sec(audio_path: str) -> float:
    """Get duration in seconds using pydub."""
    try:
        from pydub import AudioSegment
    except ImportError:
        logger.warning("pydub not installed, cannot get duration")
        return 0.0
    try:
        audio = AudioSegment.from_file(audio_path)
        return len(audio) / 1000.0
    except Exception as e:
        logger.warning("Failed to get duration for %s: %s", audio_path, e)
        return 0.0


def split_audio_into_chunk_paths(
    audio_path: str, chunk_duration_sec: int
) -> list[tuple[str, float]]:
    """
    Split audio into chunks of chunk_duration_sec (seconds).
    Returns list of (temp_file_path, start_offset_sec) for each chunk.
    Caller must unlink temp files when done.
    """
    try:
        from pydub import AudioSegment
    except ImportError:
        logger.warning("pydub not installed, cannot split long audio")
        return []
    path = Path(audio_path)
    if not path.exists():
        return []
    try:
        audio = AudioSegment.from_file(str(path))
    except Exception as e:
        logger.warning("Failed to load audio %s: %s", audio_path, e)
        return []
    total_ms = len(audio)
    chunk_ms = chunk_duration_sec * 1000
    if total_ms <= chunk_ms:
        return []
    out: list[tuple[str, float]] = []
    start_ms = 0
    idx = 0
    while start_ms < total_ms:
        end_ms = min(start_ms + chunk_ms, total_ms)
        segment = audio[start_ms:end_ms]
        fd, tmp = tempfile.mkstemp(suffix=".wav")
        try:
            import os
            os.close(fd)
            segment.export(tmp, format="wav")
            out.append((tmp, start_ms / 1000.0))
        except Exception as e:
            logger.warning("Failed to export chunk %s: %s", idx, e)
            try:
                import os
                os.unlink(tmp)
            except OSError:
                pass
        start_ms = end_ms
        idx += 1
    return out


def normalize_segments(segments: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Convert Whisper-style segments to [{id, start, end, text}, ...] with sequential ids."""
    if not segments:
        return []
    out = []
    for i, s in enumerate(segments):
        start = s.get("start")
        end = s.get("end")
        if start is None or end is None:
            continue
        try:
            start_f = float(start)
            end_f = float(end)
        except (TypeError, ValueError):
            continue
        text = (s.get("text") or s.get("content") or "").strip()
        out.append({
            "id": i + 1,
            "start": round(start_f, 2),
            "end": round(end_f, 2),
            "text": text,
        })
    return out


def merge_chunk_segments(
    chunk_results: list[tuple[list[dict[str, Any]], str, float]],
) -> tuple[list[dict[str, Any]], str]:
    """
    Merge (segments, raw_text, offset_sec) from multiple chunks.
    offset_sec is added to each segment's start/end. Returns (merged_segments_with_global_ids, merged_raw_text).
    """
    all_segments: list[dict[str, Any]] = []
    all_text: list[str] = []
    next_id = 1
    for segs, raw, offset_sec in chunk_results:
        for s in segs:
            all_segments.append({
                "id": next_id,
                "start": round(s["start"] + offset_sec, 2),
                "end": round(s["end"] + offset_sec, 2),
                "text": s.get("text", ""),
            })
            next_id += 1
        if raw and raw.strip():
            all_text.append(raw.strip())
    return (all_segments, "\n\n".join(all_text))
