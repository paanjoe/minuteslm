"""Projects API - CRUD scoped to current user."""
from typing import List

from fastapi import APIRouter, Depends, HTTPException

from app.core.auth import get_current_user_id
from app.core.database import get_db
from app.models import Meeting, Project, Template
from app.schemas.project import ProjectCreate, ProjectListResponse, ProjectResponse, ProjectUpdate
from sqlalchemy.orm import Session

router = APIRouter(prefix="/projects", tags=["projects"])


@router.get("", response_model=List[ProjectListResponse])
def list_projects(
    user_id: int = Depends(get_current_user_id),
    db: Session = Depends(get_db),
):
    """List all projects for the current user."""
    projects = (
        db.query(Project)
        .filter(Project.user_id == user_id)
        .order_by(Project.created_at.desc())
        .all()
    )
    return projects


@router.post("", response_model=ProjectResponse)
def create_project(
    payload: ProjectCreate,
    user_id: int = Depends(get_current_user_id),
    db: Session = Depends(get_db),
):
    """Create a new project."""
    project = Project(user_id=user_id, name=payload.name)
    db.add(project)
    db.commit()
    db.refresh(project)
    return project


@router.get("/{project_id}", response_model=ProjectResponse)
def get_project(
  project_id: int,
  user_id: int = Depends(get_current_user_id),
  db: Session = Depends(get_db),
):
    """Get a single project."""
    project = (
        db.query(Project)
        .filter(Project.id == project_id, Project.user_id == user_id)
        .first()
    )
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    return project


@router.patch("/{project_id}", response_model=ProjectResponse)
def update_project(
  project_id: int,
  payload: ProjectUpdate,
  user_id: int = Depends(get_current_user_id),
  db: Session = Depends(get_db),
):
    """Update project (name and/or default minutes template)."""
    project = (
        db.query(Project)
        .filter(Project.id == project_id, Project.user_id == user_id)
        .first()
    )
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    if payload.name is not None:
        project.name = payload.name
    if payload.default_template_id is not None:
        tid = payload.default_template_id if payload.default_template_id else None
        if tid:
            t = (
                db.query(Template)
                .filter(Template.id == tid, Template.user_id == user_id)
                .first()
            )
            if not t:
                raise HTTPException(status_code=404, detail="Template not found")
        project.default_template_id = tid
    db.commit()
    db.refresh(project)
    return project


@router.delete("/{project_id}")
def delete_project(
  project_id: int,
  user_id: int = Depends(get_current_user_id),
  db: Session = Depends(get_db),
):
    """Delete a project and its meetings."""
    project = (
        db.query(Project)
        .filter(Project.id == project_id, Project.user_id == user_id)
        .first()
    )
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    db.delete(project)
    db.commit()
    return {"ok": True}
