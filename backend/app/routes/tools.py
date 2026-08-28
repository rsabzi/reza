"""Tool discovery, policy, and invocation API."""

from typing import Any

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..database import get_db
from ..models import Task, Tool
from ..schemas import StepRead
from ..services.permissions import (
    ToolDisabledError,
    ToolExecutionError,
    ToolNotFoundError,
    get_tool_record,
    invoke_tool,
    sync_registered_tools,
)
from ..tools.registry import ToolArgumentError, ToolContext, call_tool

router = APIRouter(prefix="/tools", tags=["tools"])


class ToolRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    description: str
    requires_approval: bool
    enabled: bool


class ToolPolicyUpdate(BaseModel):
    requires_approval: bool | None = None
    enabled: bool | None = None


class ToolInvoke(BaseModel):
    task_id: int
    arguments: dict[str, Any] = Field(default_factory=dict)
    title: str | None = Field(default=None, min_length=1, max_length=255)


@router.get("", response_model=list[ToolRead])
def list_tools(db: Session = Depends(get_db)) -> list[Tool]:
    sync_registered_tools(db)
    return list(db.scalars(select(Tool).order_by(Tool.name)))


@router.patch("/{tool_name}", response_model=ToolRead)
def update_tool_policy(
    tool_name: str, payload: ToolPolicyUpdate, db: Session = Depends(get_db)
) -> Tool:
    try:
        _, record = get_tool_record(db, tool_name)
    except ToolNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    values = payload.model_dump(exclude_unset=True)
    if not values:
        raise HTTPException(status_code=422, detail="At least one policy field is required")
    for field, value in values.items():
        setattr(record, field, value)
    db.commit()
    db.refresh(record)
    return record


@router.post("/{tool_name}/invoke", response_model=StepRead, status_code=status.HTTP_201_CREATED)
async def invoke_tool_endpoint(tool_name: str, payload: ToolInvoke, db: Session = Depends(get_db)):
    task = db.get(Task, payload.task_id)
    if task is None:
        raise HTTPException(status_code=404, detail="Task not found")
    try:
        return await invoke_tool(
            db,
            task=task,
            tool_name=tool_name,
            arguments=payload.arguments,
            title=payload.title,
        )
    except ToolNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ToolDisabledError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc
    except ToolArgumentError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except ToolExecutionError as exc:
        raise HTTPException(
            status_code=502,
            detail={"message": f"Tool execution failed: {exc}", "step_id": exc.step.id},
        ) from exc


# Pure text-builder tools with no side effects; safe to draft inline in the UI
# without creating a Task/Step or pausing for approval.
PREVIEWABLE_TOOLS: frozenset[str] = frozenset(
    {
        "generate_outreach_script",
        "prepare_salon_outreach",
        "draft_project_proposal",
    }
)


class ToolPreview(BaseModel):
    arguments: dict[str, Any] = Field(default_factory=dict)


@router.post("/{tool_name}/preview")
async def preview_tool_endpoint(
    tool_name: str, payload: ToolPreview, db: Session = Depends(get_db)
) -> dict[str, Any]:
    """Run a side-effect-free draft tool and return its text immediately."""

    if tool_name not in PREVIEWABLE_TOOLS:
        raise HTTPException(
            status_code=403,
            detail="این ابزار پیش‌نمایش فوری ندارد؛ از اجرای عادی تسک استفاده کنید",
        )
    sync_registered_tools(db)
    try:
        registered, policy = get_tool_record(db, tool_name)
    except ToolNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    if not policy.enabled:
        raise HTTPException(status_code=403, detail=f"Tool '{tool_name}' is disabled")
    try:
        result = await call_tool(
            registered, ToolContext(db=db, task=None, step=None), payload.arguments
        )
    except ToolArgumentError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return {"tool": tool_name, "result": result}
