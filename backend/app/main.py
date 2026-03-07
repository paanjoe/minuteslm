"""FastAPI application entry point."""
from contextlib import asynccontextmanager

from sqlalchemy import text
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.auth import router as auth_router
from app.api.meetings import router as meetings_router
from app.api.projects import router as projects_router
from app.api.purge import router as purge_router
from app.api.speakers import router as speakers_router
from app.api.templates import router as templates_router
from app.api.users import router as users_router
from app.core.config import settings
from app.core.database import SessionLocal, engine, Base
from app.models import User


def _ensure_meetings_project_id():
    """Add project_id to meetings if missing (existing DBs created before projects)."""
    with engine.connect() as conn:
        r = conn.execute(
            text(
                "SELECT 1 FROM information_schema.columns "
                "WHERE table_name = 'meetings' AND column_name = 'project_id'"
            )
        )
        if r.fetchone() is None:
            conn.execute(text("ALTER TABLE meetings ADD COLUMN project_id INTEGER REFERENCES projects(id)"))
            conn.commit()


def _ensure_template_columns():
    """Add user_id, project_id to templates if missing."""
    with engine.connect() as conn:
        for col, fk in [("user_id", "REFERENCES users(id)"), ("project_id", "REFERENCES projects(id)")]:
            r = conn.execute(
                text(
                    "SELECT 1 FROM information_schema.columns "
                    "WHERE table_name = 'templates' AND column_name = :col"
                ),
                {"col": col},
            )
            if r.fetchone() is None:
                if col == "user_id":
                    conn.execute(text("ALTER TABLE templates ADD COLUMN user_id INTEGER NOT NULL DEFAULT 1 REFERENCES users(id)"))
                else:
                    conn.execute(text(f"ALTER TABLE templates ADD COLUMN {col} INTEGER {fk}"))
                conn.commit()


def _ensure_project_default_template():
    """Add default_template_id to projects if missing."""
    with engine.connect() as conn:
        r = conn.execute(
            text(
                "SELECT 1 FROM information_schema.columns "
                "WHERE table_name = 'projects' AND column_name = 'default_template_id'"
            )
        )
        if r.fetchone() is None:
            conn.execute(text("ALTER TABLE projects ADD COLUMN default_template_id INTEGER REFERENCES templates(id)"))
            conn.commit()


def _ensure_meetings_template_id():
    """Add template_id to meetings if missing."""
    with engine.connect() as conn:
        r = conn.execute(
            text(
                "SELECT 1 FROM information_schema.columns "
                "WHERE table_name = 'meetings' AND column_name = 'template_id'"
            )
        )
        if r.fetchone() is None:
            conn.execute(text("ALTER TABLE meetings ADD COLUMN template_id INTEGER REFERENCES templates(id)"))
            conn.commit()


def _ensure_template_file_columns():
    """Add file_path, file_name, sample_content, section_titles to templates if missing."""
    with engine.connect() as conn:
        for col, col_type in [
            ("file_path", "VARCHAR(512)"),
            ("file_name", "VARCHAR(255)"),
            ("sample_content", "TEXT"),
            ("section_titles", "JSONB"),
        ]:
            r = conn.execute(
                text(
                    "SELECT 1 FROM information_schema.columns "
                    "WHERE table_name = 'templates' AND column_name = :col"
                ),
                {"col": col},
            )
            if r.fetchone() is None:
                conn.execute(text(f"ALTER TABLE templates ADD COLUMN {col} {col_type}"))
                conn.commit()


def _ensure_transcript_segments():
    """Add segments (JSONB) to transcripts if missing."""
    with engine.connect() as conn:
        r = conn.execute(
            text(
                "SELECT 1 FROM information_schema.columns "
                "WHERE table_name = 'transcripts' AND column_name = 'segments'"
            )
        )
        if r.fetchone() is None:
            conn.execute(text("ALTER TABLE transcripts ADD COLUMN segments JSONB"))
            conn.commit()


def _ensure_template_format_spec_markdown():
    """Add format_spec_markdown to templates if missing."""
    with engine.connect() as conn:
        r = conn.execute(
            text(
                "SELECT 1 FROM information_schema.columns "
                "WHERE table_name = 'templates' AND column_name = 'format_spec_markdown'"
            )
        )
        if r.fetchone() is None:
            conn.execute(text("ALTER TABLE templates ADD COLUMN format_spec_markdown TEXT"))
            conn.commit()


def _ensure_meeting_metadata_columns():
    """Add discussion_date_time, attendee, absentees, minutes_taken_by to meetings if missing."""
    with engine.connect() as conn:
        for col, col_type in [
            ("discussion_date_time", "TIMESTAMP WITH TIME ZONE"),
            ("attendee", "TEXT"),
            ("absentees", "TEXT"),
            ("minutes_taken_by", "VARCHAR(255)"),
        ]:
            r = conn.execute(
                text(
                    "SELECT 1 FROM information_schema.columns "
                    "WHERE table_name = 'meetings' AND column_name = :col"
                ),
                {"col": col},
            )
            if r.fetchone() is None:
                conn.execute(text(f"ALTER TABLE meetings ADD COLUMN {col} {col_type}"))
                conn.commit()


def _ensure_meeting_summary_context():
    """Add summary_context to meetings if missing."""
    with engine.connect() as conn:
        r = conn.execute(
            text(
                "SELECT 1 FROM information_schema.columns "
                "WHERE table_name = 'meetings' AND column_name = 'summary_context'"
            )
        )
        if r.fetchone() is None:
            conn.execute(text("ALTER TABLE meetings ADD COLUMN summary_context TEXT"))
            conn.commit()


def _ensure_meeting_status_transcribed():
    """Add 'transcribed' and 'TRANSCRIBED' to meetingstatus enum if missing (DB may use lowercase or uppercase)."""
    with engine.connect() as conn:
        for label in ("transcribed", "TRANSCRIBED"):
            r = conn.execute(
                text(
                    "SELECT 1 FROM pg_enum e "
                    "JOIN pg_type t ON e.enumtypid = t.oid "
                    "WHERE t.typname = 'meetingstatus' AND e.enumlabel = :label"
                ),
                {"label": label},
            )
            if r.fetchone() is None:
                # Use literal label (safe: only our two fixed strings)
                sql = "ALTER TYPE meetingstatus ADD VALUE 'transcribed'" if label == "transcribed" else "ALTER TYPE meetingstatus ADD VALUE 'TRANSCRIBED'"
                conn.execute(text(sql))
                conn.commit()


def _ensure_user_token():
    """Add token column to users if missing."""
    with engine.connect() as conn:
        r = conn.execute(
            text(
                "SELECT 1 FROM information_schema.columns "
                "WHERE table_name = 'users' AND column_name = 'token'"
            )
        )
        if r.fetchone() is None:
            conn.execute(text("ALTER TABLE users ADD COLUMN token VARCHAR(256)"))
            conn.commit()


def _sync_users_id_sequence():
    """Sync the users.id sequence to max(id) so new inserts get correct next id (fixes duplicate key on id=1)."""
    with engine.connect() as conn:
        conn.execute(
            text(
                "SELECT setval(pg_get_serial_sequence('users', 'id'), "
                "COALESCE((SELECT MAX(id) FROM users), 1))"
            )
        )
        conn.commit()


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Create tables and seed dummy admin user."""
    Base.metadata.create_all(bind=engine)
    _ensure_meetings_project_id()
    _ensure_template_columns()
    _ensure_project_default_template()
    _ensure_meetings_template_id()
    _ensure_template_file_columns()
    _ensure_transcript_segments()
    _ensure_template_format_spec_markdown()
    _ensure_meeting_metadata_columns()
    _ensure_meeting_summary_context()
    _ensure_meeting_status_transcribed()
    _ensure_user_token()
    db = SessionLocal()
    try:
        admin = db.query(User).filter(User.username == settings.admin_username).first()
        if not admin:
            admin = User(
                username=settings.admin_username,
                password=settings.admin_password,
            )
            db.add(admin)
            db.commit()
        _sync_users_id_sequence()
    finally:
        db.close()
    yield


app = FastAPI(
    title="MinutesLM",
    description="Local LLM Meeting Minutes Taker",
    version="0.1.0",
    lifespan=lifespan,
)

_cors_origins = [o.strip() for o in settings.cors_origins.split(",") if o.strip()] or ["*"]
app.add_middleware(
    CORSMiddleware,
    allow_origins=_cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth_router)
app.include_router(projects_router)
app.include_router(templates_router)
app.include_router(meetings_router)
app.include_router(speakers_router)
app.include_router(purge_router)
app.include_router(users_router)


@app.get("/health")
def health():
    """Health check."""
    return {"status": "ok"}


@app.get("/config")
def get_config():
    """Public config for UI (e.g. AI model name). Called as /api/config via proxy."""
    return {"ollama_model": settings.ollama_model}
