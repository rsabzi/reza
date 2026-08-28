"""Recurring task control endpoints."""

from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from ..database import get_db
from ..models import Task
from ..scheduler import (
    materialize_recurring_task,
    process_due_recurring_tasks,
    scheduler_running,
)
from ..schemas import TaskDetail, TaskRead

router = APIRouter(tags=["scheduler"])


class RunDueRequest(BaseModel):
    now: datetime | None = None


@router.post(
    "/tasks/{task_id}/run-now",
    response_model=TaskDetail,
    status_code=status.HTTP_201_CREATED,
)
def run_task_now(task_id: int, db: Session = Depends(get_db)) -> Task:
    template = db.get(Task, task_id)
    if template is None:
        raise HTTPException(status_code=404, detail="Task not found")
    try:
        instance = materialize_recurring_task(db, template)
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    return db.scalar(select(Task).options(selectinload(Task.steps)).where(Task.id == instance.id))


@router.post(
    "/scheduler/run-due",
    response_model=list[TaskRead],
    status_code=status.HTTP_201_CREATED,
)
def run_due(payload: RunDueRequest, db: Session = Depends(get_db)) -> list[Task]:
    return process_due_recurring_tasks(db, now=payload.now)


@router.get("/scheduler/status")
def scheduler_status() -> dict[str, bool | str]:
    return {"running": scheduler_running(), "poll_interval": "30 seconds"}
