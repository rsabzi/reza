"""Planning, execution, and approval APIs."""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from ..agent.ai_client import AIConfigurationError, ChatClient, get_ai_client
from ..agent.executor import ExecutionError, execute_task
from ..agent.planner import PlanningError, decompose_task
from ..database import get_db
from ..models import AgentActionRun, AILog, Step, Task, utcnow
from ..schemas import StepRead, TaskDetail

router = APIRouter(tags=["agent"])


def _task_detail(db: Session, task_id: int) -> Task:
    task = db.scalar(select(Task).options(selectinload(Task.steps)).where(Task.id == task_id))
    if task is None:
        raise HTTPException(status_code=404, detail="Task not found")
    return task


@router.post(
    "/tasks/{task_id}/plan",
    response_model=list[StepRead],
    status_code=status.HTTP_201_CREATED,
)
async def plan_task(
    task_id: int,
    db: Session = Depends(get_db),
    ai_client: ChatClient = Depends(get_ai_client),
):
    task = db.get(Task, task_id)
    if task is None:
        raise HTTPException(status_code=404, detail="Task not found")
    try:
        return await decompose_task(db, task, ai_client)
    except AIConfigurationError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except PlanningError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc


@router.post("/tasks/{task_id}/execute", response_model=TaskDetail)
async def execute_task_endpoint(task_id: int, db: Session = Depends(get_db)) -> Task:
    if db.get(Task, task_id) is None:
        raise HTTPException(status_code=404, detail="Task not found")
    try:
        await execute_task(db, task_id)
    except ExecutionError as exc:
        raise HTTPException(
            status_code=502,
            detail={"message": str(exc), "step_id": exc.step_id},
        ) from exc
    return _task_detail(db, task_id)


@router.post("/steps/{step_id}/approve", response_model=TaskDetail)
async def approve_step(step_id: int, db: Session = Depends(get_db)) -> Task:
    step = db.get(Step, step_id)
    if step is None:
        raise HTTPException(status_code=404, detail="Step not found")
    if step.status != "needs_approval":
        raise HTTPException(status_code=409, detail="Step is not waiting for approval")
    step.approved_at = utcnow()
    step.status = "pending"
    step.error = None
    db.commit()
    try:
        await execute_task(db, step.task_id)
    except ExecutionError as exc:
        raise HTTPException(
            status_code=502, detail={"message": str(exc), "step_id": exc.step_id}
        ) from exc
    return _task_detail(db, step.task_id)


@router.post("/steps/{step_id}/reject", response_model=TaskDetail)
def reject_step(step_id: int, db: Session = Depends(get_db)) -> Task:
    step = db.get(Step, step_id)
    if step is None:
        raise HTTPException(status_code=404, detail="Step not found")
    if step.status != "needs_approval":
        raise HTTPException(status_code=409, detail="Step is not waiting for approval")
    step.status = "cancelled"
    step.error = "Rejected by user"
    step.task.status = "cancelled"
    action_run = db.scalar(select(AgentActionRun).where(AgentActionRun.step_id == step.id).limit(1))
    if action_run is not None and action_run.status == "needs_approval":
        action_run.status = "failed"
        action_run.error = "Rejected by user"
        action_run.finished_at = utcnow()
    db.commit()
    return _task_detail(db, step.task_id)


@router.get("/ai-logs")
def list_ai_logs(task_id: int | None = None, db: Session = Depends(get_db)) -> list[dict]:
    statement = select(AILog).order_by(AILog.created_at.desc(), AILog.id.desc())
    if task_id is not None:
        statement = statement.where(AILog.task_id == task_id)
    logs = list(db.scalars(statement.limit(200)))
    return [
        {
            "id": log.id,
            "task_id": log.task_id,
            "operation": log.operation,
            "model": log.model,
            "prompt": log.prompt,
            "response": log.response,
            "error": log.error,
            "attempt": log.attempt,
            "created_at": log.created_at,
        }
        for log in logs
    ]
