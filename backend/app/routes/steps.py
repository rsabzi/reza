"""Step CRUD API."""

from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from ..database import get_db
from ..memory.embedder import EmbeddingError
from ..memory.store import save_completed_step
from ..models import Step, Task
from ..schemas import StepCreate, StepRead, StepUpdate

router = APIRouter(prefix="/steps", tags=["steps"])


@router.post("", response_model=StepRead, status_code=status.HTTP_201_CREATED)
def create_step(payload: StepCreate, db: Session = Depends(get_db)) -> Step:
    task = db.get(Task, payload.task_id)
    if task is None:
        raise HTTPException(status_code=404, detail="Parent task not found")
    step = Step(**payload.model_dump())
    db.add(step)
    if payload.status == "pending" and task.status in {"done", "cancelled", "failed"}:
        task.status = "pending"
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(
            status_code=409,
            detail="A step with this position already exists for the task",
        ) from exc
    db.refresh(step)
    return step


@router.get("", response_model=list[StepRead])
def list_steps(
    task_id: int | None = None,
    step_status: str | None = None,
    db: Session = Depends(get_db),
) -> list[Step]:
    statement = select(Step).order_by(Step.task_id, Step.position)
    if task_id is not None:
        if db.get(Task, task_id) is None:
            raise HTTPException(status_code=404, detail="Parent task not found")
        statement = statement.where(Step.task_id == task_id)
    if step_status is not None:
        statement = statement.where(Step.status == step_status)
    return list(db.scalars(statement))


@router.get("/{step_id}", response_model=StepRead)
def get_step(step_id: int, db: Session = Depends(get_db)) -> Step:
    step = db.get(Step, step_id)
    if step is None:
        raise HTTPException(status_code=404, detail="Step not found")
    return step


@router.patch("/{step_id}", response_model=StepRead)
def update_step(step_id: int, payload: StepUpdate, db: Session = Depends(get_db)) -> Step:
    step = db.get(Step, step_id)
    if step is None:
        raise HTTPException(status_code=404, detail="Step not found")
    was_done = step.status == "done"
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(step, field, value)
    try:
        db.flush()
        if step.status == "done" and step.result is not None and not was_done:
            save_completed_step(db, step, commit=False)
        if step.status == "done":
            unfinished = db.scalar(
                select(func.count(Step.id)).where(
                    Step.task_id == step.task_id,
                    Step.status != "done",
                )
            )
            if unfinished == 0:
                step.task.status = "done"
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(
            status_code=409,
            detail="A step with this position already exists for the task",
        ) from exc
    except (EmbeddingError, ValueError) as exc:
        db.rollback()
        raise HTTPException(
            status_code=502, detail=f"Could not save step result to memory: {exc}"
        ) from exc
    db.refresh(step)
    return step


@router.delete("/{step_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_step(step_id: int, db: Session = Depends(get_db)) -> Response:
    step = db.get(Step, step_id)
    if step is None:
        raise HTTPException(status_code=404, detail="Step not found")
    db.delete(step)
    db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)
