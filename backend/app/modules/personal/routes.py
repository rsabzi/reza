"""Personal/freelance project APIs."""

from __future__ import annotations

from datetime import date

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from ...database import get_db
from .models import PersonalProject
from .schemas import ProjectCreate, ProjectRead, ProjectUpdate, ReminderItem
from .service import (
    InvalidStatusTransition,
    daily_personal_reminder,
    validate_status_transition,
)

router = APIRouter(prefix="/personal", tags=["personal module"])


@router.get("/reminders", response_model=list[ReminderItem])
def get_reminders(
    today: date | None = None,
    within_days: int = Query(default=3, ge=0, le=365),
    db: Session = Depends(get_db),
) -> list[dict]:
    return daily_personal_reminder(db, today=today, within_days=within_days)


@router.post("/projects", response_model=ProjectRead, status_code=status.HTTP_201_CREATED)
def create_project(payload: ProjectCreate, db: Session = Depends(get_db)) -> PersonalProject:
    project = PersonalProject(**payload.model_dump())
    db.add(project)
    db.commit()
    db.refresh(project)
    return project


@router.get("/projects", response_model=list[ProjectRead])
def list_projects(
    project_status: str | None = Query(default=None, alias="status"),
    db: Session = Depends(get_db),
) -> list[PersonalProject]:
    statement = select(PersonalProject).order_by(
        PersonalProject.due_date.is_(None), PersonalProject.due_date, PersonalProject.id
    )
    if project_status:
        statement = statement.where(PersonalProject.status == project_status)
    return list(db.scalars(statement))


@router.get("/projects/{project_id}", response_model=ProjectRead)
def get_project(project_id: int, db: Session = Depends(get_db)) -> PersonalProject:
    project = db.get(PersonalProject, project_id)
    if project is None:
        raise HTTPException(status_code=404, detail="Personal project not found")
    return project


@router.patch("/projects/{project_id}", response_model=ProjectRead)
def update_project(
    project_id: int, payload: ProjectUpdate, db: Session = Depends(get_db)
) -> PersonalProject:
    project = db.get(PersonalProject, project_id)
    if project is None:
        raise HTTPException(status_code=404, detail="Personal project not found")
    values = payload.model_dump(exclude_unset=True)
    if "status" in values:
        try:
            validate_status_transition(project.status, values["status"])
        except InvalidStatusTransition as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc
    for field, value in values.items():
        setattr(project, field, value)
    db.commit()
    db.refresh(project)
    return project


@router.delete("/projects/{project_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_project(project_id: int, db: Session = Depends(get_db)) -> Response:
    project = db.get(PersonalProject, project_id)
    if project is None:
        raise HTTPException(status_code=404, detail="Personal project not found")
    db.delete(project)
    db.commit()
    return Response(status_code=204)
