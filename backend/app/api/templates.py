"""Templates API - minutes format templates (tied to user/project)."""
from pathlib import Path
from typing import List, Optional

from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile

from app.core.auth import get_current_user_id
from app.core.config import settings
from app.core.database import get_db
from app.models import Project, Template
from app.models.template import DEFAULT_STRUCTURE
from app.schemas.template import (
    TemplateCreate,
    TemplateListResponse,
    TemplateResponse,
    TemplateUpdate,
)
from app.services.template_extract import (
    extract_text_from_file,
    extract_headings_from_file,
    extract_headings_from_text,
)
from sqlalchemy.orm import Session

router = APIRouter(prefix="/templates", tags=["templates"])


@router.get("", response_model=List[TemplateListResponse])
def list_templates(
    project_id: Optional[int] = Query(None, description="Filter by project"),
    user_id: int = Depends(get_current_user_id),
    db: Session = Depends(get_db),
):
    """List templates for the current user, optionally filtered by project."""
    q = db.query(Template).filter(Template.user_id == user_id)
    if project_id is not None:
        q = q.filter(Template.project_id == project_id)
    return q.order_by(Template.name).all()


@router.post("", response_model=TemplateResponse)
def create_template(
    payload: TemplateCreate,
    user_id: int = Depends(get_current_user_id),
    db: Session = Depends(get_db),
):
    """Create a minutes template. Optionally tie to a project."""
    if payload.project_id is not None:
        proj = (
            db.query(Project)
            .filter(Project.id == payload.project_id, Project.user_id == user_id)
            .first()
        )
        if not proj:
            raise HTTPException(status_code=404, detail="Project not found")
    structure = payload.structure if payload.structure is not None else dict(DEFAULT_STRUCTURE)
    template = Template(
        user_id=user_id,
        project_id=payload.project_id,
        name=payload.name,
        prompt_suffix=payload.prompt_suffix,
        structure=structure,
    )
    db.add(template)
    db.commit()
    db.refresh(template)
    return template


@router.get("/{template_id}", response_model=TemplateResponse)
def get_template(
    template_id: int,
    user_id: int = Depends(get_current_user_id),
    db: Session = Depends(get_db),
):
    """Get a single template."""
    template = (
        db.query(Template)
        .filter(Template.id == template_id, Template.user_id == user_id)
        .first()
    )
    if not template:
        raise HTTPException(status_code=404, detail="Template not found")
    return template


@router.patch("/{template_id}", response_model=TemplateResponse)
def update_template(
    template_id: int,
    payload: TemplateUpdate,
    user_id: int = Depends(get_current_user_id),
    db: Session = Depends(get_db),
):
    """Update a template."""
    template = (
        db.query(Template)
        .filter(Template.id == template_id, Template.user_id == user_id)
        .first()
    )
    if not template:
        raise HTTPException(status_code=404, detail="Template not found")
    if payload.name is not None:
        template.name = payload.name
    if payload.project_id is not None:
        if payload.project_id != 0:
            proj = (
                db.query(Project)
                .filter(Project.id == payload.project_id, Project.user_id == user_id)
                .first()
            )
            if not proj:
                raise HTTPException(status_code=404, detail="Project not found")
        template.project_id = payload.project_id if payload.project_id != 0 else None
    if payload.prompt_suffix is not None:
        template.prompt_suffix = payload.prompt_suffix
    if payload.structure is not None:
        template.structure = payload.structure
    db.commit()
    db.refresh(template)
    return template


@router.delete("/{template_id}")
def delete_template(
    template_id: int,
    user_id: int = Depends(get_current_user_id),
    db: Session = Depends(get_db),
):
    """Delete a template."""
    template = (
        db.query(Template)
        .filter(Template.id == template_id, Template.user_id == user_id)
        .first()
    )
    if not template:
        raise HTTPException(status_code=404, detail="Template not found")
    db.delete(template)
    db.commit()
    return {"ok": True}


ALLOWED_TEMPLATE_EXTENSIONS = {".docx", ".txt"}  # .doc not supported by python-docx


@router.post("/{template_id}/upload", response_model=TemplateResponse)
async def upload_template_file(
    template_id: int,
    file: UploadFile = File(...),
    user_id: int = Depends(get_current_user_id),
    db: Session = Depends(get_db),
):
    """Upload a Word or text template. Text is extracted and used by the LLM to match format."""
    template = (
        db.query(Template)
        .filter(Template.id == template_id, Template.user_id == user_id)
        .first()
    )
    if not template:
        raise HTTPException(status_code=404, detail="Template not found")

    ext = Path(file.filename or "").suffix.lower()
    if ext not in ALLOWED_TEMPLATE_EXTENSIONS:
        raise HTTPException(
            status_code=400,
            detail="Use .docx or .txt (Word .doc is not supported).",
        )

    upload_dir = Path(settings.template_upload_dir)
    upload_dir.mkdir(parents=True, exist_ok=True)
    safe_name = f"template_{template_id}_{Path(file.filename or 'file').name}"
    path = upload_dir / safe_name

    contents = await file.read()
    if len(contents) > settings.max_upload_mb * 1024 * 1024:
        raise HTTPException(
            status_code=400,
            detail=f"File too large. Max {settings.max_upload_mb}MB.",
        )
    path.write_bytes(contents)

    sample_content = extract_text_from_file(path)
    section_titles = extract_headings_from_file(path)
    # Fallback: if no headings from style/structure (e.g. Word without Heading styles), parse plain text
    if not section_titles and sample_content:
        section_titles = extract_headings_from_text(sample_content)
    template.file_path = str(path)
    template.file_name = Path(file.filename or "file").name
    template.sample_content = sample_content[:50000] if sample_content else None
    template.section_titles = section_titles if section_titles else None
    db.commit()
    db.refresh(template)
    return template
