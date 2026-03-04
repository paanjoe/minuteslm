"""FastAPI application entry point."""
from contextlib import asynccontextmanager

from sqlalchemy import text
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.auth import router as auth_router
from app.api.meetings import router as meetings_router
from app.api.projects import router as projects_router
from app.api.speakers import router as speakers_router
from app.api.templates import router as templates_router
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


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Create tables and seed dummy admin user."""
    Base.metadata.create_all(bind=engine)
    _ensure_meetings_project_id()
    _ensure_template_columns()
    _ensure_project_default_template()
    _ensure_meetings_template_id()
    _ensure_template_file_columns()
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
    finally:
        db.close()
    yield


app = FastAPI(
    title="MinutesLM",
    description="Local LLM Meeting Minutes Taker",
    version="0.1.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth_router)
app.include_router(projects_router)
app.include_router(templates_router)
app.include_router(meetings_router)
app.include_router(speakers_router)


@app.get("/health")
def health():
    """Health check."""
    return {"status": "ok"}
