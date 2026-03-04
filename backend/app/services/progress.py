"""In-memory progress store for meeting processing."""
_progress: dict[int, str] = {}


def set_progress(meeting_id: int, message: str) -> None:
    _progress[meeting_id] = message


def get_progress(meeting_id: int) -> str | None:
    return _progress.get(meeting_id)


def clear_progress(meeting_id: int) -> None:
    _progress.pop(meeting_id, None)
