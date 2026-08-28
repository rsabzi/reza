"""Sequential, approval-aware task executor."""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from ..memory.store import save_completed_step
from ..models import Step, Task
from ..services.permissions import ToolDisabledError, ToolNotFoundError, get_tool_record
from ..tools.registry import ToolContext, call_tool


class ExecutionError(RuntimeError):
    def __init__(self, message: str, step_id: int | None = None):
        super().__init__(message)
        self.step_id = step_id


async def _execute_tool_step(db: Session, task: Task, step: Step) -> bool:
    """Execute one step. Return False when execution must pause."""

    if not step.tool_name:
        step.status = "waiting_for_user"
        step.error = "No automated tool was selected; user input is required"
        task.status = "paused"
        db.commit()
        return False

    try:
        registered, policy = get_tool_record(db, step.tool_name)
        if not policy.enabled:
            raise ToolDisabledError(f"Tool '{step.tool_name}' is disabled")
    except (ToolNotFoundError, ToolDisabledError) as exc:
        step.status = "failed"
        step.error = str(exc)
        task.status = "failed"
        db.commit()
        raise ExecutionError(str(exc), step.id) from exc

    step.requires_approval = policy.requires_approval
    if policy.requires_approval and step.approved_at is None:
        step.status = "needs_approval"
        task.status = "paused"
        db.commit()
        return False

    step.status = "running"
    task.status = "running"
    db.commit()
    try:
        result = await call_tool(
            registered,
            ToolContext(db=db, task=task, step=step),
            dict(step.arguments or {}),
        )
        step.result = result
        step.status = "done"
        step.error = None
        db.flush()
        save_completed_step(db, step, commit=False)
        db.commit()
        return True
    except Exception as exc:
        db.rollback()
        step = db.get(Step, step.id)
        task = db.get(Task, task.id)
        if step is not None:
            step.status = "failed"
            step.error = str(exc) or exc.__class__.__name__
        if task is not None:
            task.status = "failed"
        db.commit()
        raise ExecutionError(str(exc) or exc.__class__.__name__, step.id if step else None) from exc


async def execute_task(db: Session, task_id: int) -> Task:
    task = db.get(Task, task_id)
    if task is None:
        raise LookupError("Task not found")
    steps = list(db.scalars(select(Step).where(Step.task_id == task.id).order_by(Step.position)))
    if not steps:
        raise ExecutionError("Task has no planned steps")

    for step in steps:
        if step.status in {"done", "cancelled"}:
            continue
        if step.status in {"needs_approval", "waiting_for_user"}:
            task.status = "paused"
            db.commit()
            return task
        completed = await _execute_tool_step(db, task, step)
        if not completed:
            # Critical invariant: later pending steps are untouched.
            return task

    task.status = "done"
    db.commit()
    db.refresh(task)
    return task
