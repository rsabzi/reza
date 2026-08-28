"""Tool policy persistence and guarded invocation."""

from __future__ import annotations

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from ..memory.store import save_completed_step
from ..models import Step, Task, Tool
from ..tools.registry import (
    RegisteredTool,
    ToolContext,
    call_tool,
    get_tool,
    list_registered_tools,
    validate_tool_arguments,
)


class ToolNotFoundError(LookupError):
    pass


class ToolDisabledError(PermissionError):
    pass


class ToolExecutionError(RuntimeError):
    def __init__(self, message: str, step: Step):
        super().__init__(message)
        self.step = step


def sync_registered_tools(db: Session) -> list[Tool]:
    """Persist registry metadata once while preserving user-edited policy flags."""

    records: list[Tool] = []
    for registered in list_registered_tools():
        record = db.scalar(select(Tool).where(Tool.name == registered.name))
        if record is None:
            record = Tool(
                name=registered.name,
                description=registered.description,
                requires_approval=registered.requires_approval,
                enabled=True,
            )
            db.add(record)
        else:
            # Description follows code; approval/enabled are user policy and remain persisted.
            record.description = registered.description
        records.append(record)
    db.commit()
    for record in records:
        db.refresh(record)
    return sorted(records, key=lambda item: item.name)


def get_tool_record(db: Session, name: str) -> tuple[RegisteredTool, Tool]:
    registered = get_tool(name)
    if registered is None:
        raise ToolNotFoundError(f"Tool '{name}' is not registered")
    sync_registered_tools(db)
    record = db.scalar(select(Tool).where(Tool.name == name))
    if record is None:  # defensive: sync_registered_tools should have created it
        raise ToolNotFoundError(f"Tool '{name}' has no persisted policy")
    return registered, record


def next_step_position(db: Session, task_id: int) -> int:
    highest = db.scalar(select(func.max(Step.position)).where(Step.task_id == task_id))
    return (highest if highest is not None else -1) + 1


async def invoke_tool(
    db: Session,
    *,
    task: Task,
    tool_name: str,
    arguments: dict,
    title: str | None = None,
) -> Step:
    """Create an auditable Step and either pause or execute according to policy."""

    registered, policy = get_tool_record(db, tool_name)
    if not policy.enabled:
        raise ToolDisabledError(f"Tool '{tool_name}' is disabled")
    validate_tool_arguments(registered, arguments)

    needs_approval = policy.requires_approval
    step = Step(
        task_id=task.id,
        title=title or f"Run {tool_name}",
        position=next_step_position(db, task.id),
        status="needs_approval" if needs_approval else "running",
        tool_name=tool_name,
        arguments=arguments,
        requires_approval=needs_approval,
    )
    db.add(step)
    task.status = "paused" if needs_approval else "running"
    db.commit()
    db.refresh(step)

    if needs_approval:
        return step

    try:
        result = await call_tool(registered, ToolContext(db=db, task=task, step=step), arguments)
        step.result = result
        step.status = "done"
        task.status = "done"
        db.flush()
        save_completed_step(db, step, commit=False)
        db.commit()
        db.refresh(step)
        return step
    except Exception as exc:
        db.rollback()
        persisted_step = db.get(Step, step.id)
        persisted_task = db.get(Task, task.id)
        if persisted_step is not None:
            persisted_step.status = "failed"
            persisted_step.error = str(exc) or exc.__class__.__name__
        if persisted_task is not None:
            persisted_task.status = "failed"
        db.commit()
        if persisted_step is None:
            raise ToolExecutionError(str(exc) or exc.__class__.__name__, step) from exc
        db.refresh(persisted_step)
        raise ToolExecutionError(
            persisted_step.error or "Tool execution failed", persisted_step
        ) from exc
