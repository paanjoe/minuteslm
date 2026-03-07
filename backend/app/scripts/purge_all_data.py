"""
Purge all data from the database and upload directories.
Run from the backend directory: python -m app.scripts.purge_all_data
Or from project root: cd backend && python -m app.scripts.purge_all_data
"""
import sys

# Ensure we run with backend as cwd so upload paths resolve correctly
from pathlib import Path

backend_dir = Path(__file__).resolve().parent.parent.parent
if Path.cwd() != backend_dir:
    import os
    os.chdir(backend_dir)

from app.core.config import settings
from app.core.database import SessionLocal
from app.services.purge import purge_all_data


def main() -> int:
    print("This will delete ALL projects, meetings, transcripts, minutes, speakers, templates, and uploaded files.")
    if input("Type 'yes' to confirm: ").strip().lower() != "yes":
        print("Aborted.")
        return 0
    db = SessionLocal()
    try:
        result = purge_all_data(db, settings)
        print(
            f"Done. Deleted {result['deleted_rows']} DB rows and {result['deleted_files']} files "
            f"(meetings: {result['deleted_meetings']}, projects: {result['deleted_projects']}, "
            f"speakers: {result['deleted_speakers']}, templates: {result['deleted_templates']})."
        )
        return 0
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        return 1
    finally:
        db.close()


if __name__ == "__main__":
    sys.exit(main())
