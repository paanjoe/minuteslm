"""Purge all user data: database rows and uploaded files."""
import logging
from pathlib import Path

from sqlalchemy.orm import Session

from app.core.config import Settings
from app.models import (
    ActionItem,
    Meeting,
    MeetingSpeakerSnippet,
    Minute,
    Project,
    Speaker,
    Template,
    Transcript,
)

logger = logging.getLogger(__name__)


def _clear_upload_dir(dir_path: Path) -> int:
    """Remove all files under dir_path (non-recursive for top-level only, or recursive). Returns count removed."""
    if not dir_path.exists() or not dir_path.is_dir():
        return 0
    count = 0
    for p in dir_path.iterdir():
        if p.is_file():
            try:
                p.unlink()
                count += 1
            except OSError as e:
                logger.warning("Could not delete %s: %s", p, e)
        elif p.is_dir():
            for q in p.rglob("*"):
                if q.is_file():
                    try:
                        q.unlink()
                        count += 1
                    except OSError as e:
                        logger.warning("Could not delete %s: %s", q, e)
            try:
                for q in sorted(p.rglob("*"), key=lambda x: -len(x.parts)):
                    if q.is_dir():
                        q.rmdir()
                p.rmdir()
            except OSError as e:
                logger.warning("Could not remove dir %s: %s", p, e)
    return count


def purge_all_data(db: Session, settings: Settings) -> dict[str, int]:
    """
    Delete all projects, meetings, transcripts, minutes, action items,
    speaker snippets, speakers, templates, and all files in upload dirs.
    Leaves users table intact so login still works.
    Returns counts of deleted rows and deleted files.
    """
    # Null FK so we can delete templates and projects
    db.query(Project).update({Project.default_template_id: None})
    db.commit()

    # Delete in dependency order (child tables first for bulk delete)
    deleted_action_items = db.query(ActionItem).delete()
    deleted_minutes = db.query(Minute).delete()
    deleted_transcripts = db.query(Transcript).delete()
    deleted_snippets = db.query(MeetingSpeakerSnippet).delete()
    deleted_meetings = db.query(Meeting).delete()
    deleted_speakers = db.query(Speaker).delete()
    deleted_templates = db.query(Template).delete()
    deleted_projects = db.query(Project).delete()
    db.commit()

    # Clear upload directories (paths may be relative to cwd when server runs)
    base = Path.cwd()
    audio_dir = (settings.audio_upload_dir if settings.audio_upload_dir.is_absolute() else base / settings.audio_upload_dir)
    speakers_dir = (settings.speaker_samples_dir if settings.speaker_samples_dir.is_absolute() else base / settings.speaker_samples_dir)
    templates_dir = (settings.template_upload_dir if settings.template_upload_dir.is_absolute() else base / settings.template_upload_dir)
    detected_dir = (settings.detected_snippets_dir if settings.detected_snippets_dir.is_absolute() else base / settings.detected_snippets_dir)

    files_audio = _clear_upload_dir(audio_dir)
    files_speakers = _clear_upload_dir(speakers_dir)
    files_templates = _clear_upload_dir(templates_dir)
    files_detected = _clear_upload_dir(detected_dir)

    total_rows = (
        deleted_action_items + deleted_minutes + deleted_transcripts
        + deleted_snippets + deleted_meetings + deleted_speakers
        + deleted_templates + deleted_projects
    )
    total_files = files_audio + files_speakers + files_templates + files_detected
    logger.info(
        "Purge complete: %s DB rows, %s files",
        total_rows,
        total_files,
    )
    return {
        "deleted_rows": total_rows,
        "deleted_files": total_files,
        "deleted_meetings": deleted_meetings,
        "deleted_projects": deleted_projects,
        "deleted_speakers": deleted_speakers,
        "deleted_templates": deleted_templates,
    }
