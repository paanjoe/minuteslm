"""In-memory progress store for meeting processing (message + optional percentage 0-100)."""
from typing import Optional

_progress: dict[int, tuple[str, Optional[int]]] = {}


def set_progress(meeting_id: int, message: str, percentage: Optional[int] = None) -> None:
    _progress[meeting_id] = (message, percentage)


def get_progress(meeting_id: int) -> tuple[Optional[str], Optional[int]]:
    val = _progress.get(meeting_id)
    if val is None:
        return (None, None)
    return val


def clear_progress(meeting_id: int) -> None:
    _progress.pop(meeting_id, None)
