"""Memory-aware task decomposition with fully auditable AI calls."""

from __future__ import annotations

import asyncio
import json
from collections.abc import Awaitable, Callable
from typing import Any

from sqlalchemy import delete
from sqlalchemy.orm import Session

from ..memory.store import search_memory
from ..models import AILog, Step, Task
from ..tools.registry import list_registered_tools
from .ai_client import AI_MODEL, AIClient


class PlanningError(RuntimeError):
    pass


def _strip_json_fence(value: str) -> str:
    stripped = value.strip()
    if stripped.startswith("```"):
        lines = stripped.splitlines()
        if lines and lines[0].startswith("```"):
            lines = lines[1:]
        if lines and lines[-1].strip() == "```":
            lines = lines[:-1]
        return "\n".join(lines).strip()
    return stripped


def parse_plan_response(
    response: str | dict[str, Any] | list[Any],
) -> list[dict[str, Any]]:
    if isinstance(response, str):
        try:
            parsed = json.loads(_strip_json_fence(response))
        except json.JSONDecodeError as exc:
            raise PlanningError(f"AI returned invalid JSON: {exc.msg}") from exc
    else:
        parsed = response
    if isinstance(parsed, dict):
        parsed = parsed.get("steps")
    if not isinstance(parsed, list) or not parsed:
        raise PlanningError("AI plan must contain a non-empty 'steps' list")

    normalized: list[dict[str, Any]] = []
    for index, item in enumerate(parsed):
        if not isinstance(item, dict):
            raise PlanningError(f"Plan step {index} must be an object")
        title = str(item.get("title", "")).strip()
        if not title:
            raise PlanningError(f"Plan step {index} is missing a title")
        arguments = item.get("arguments", {})
        if not isinstance(arguments, dict):
            raise PlanningError(f"Plan step {index} arguments must be an object")
        normalized.append(
            {
                "title": title,
                "description": item.get("description"),
                "tool_name": item.get("tool_name"),
                "arguments": arguments,
            }
        )
    return normalized


def _build_prompt(task: Task, memories: list[str]) -> str:
    tools = [
        {
            "name": item.name,
            "description": item.description,
            "default_requires_approval": item.requires_approval,
        }
        for item in list_registered_tools()
    ]
    return (
        "You are the planner for a local single-user AI agent. Decompose the task into "
        "small executable steps. Use registered tool names exactly when a tool applies. "
        "If a step cannot be automated, omit tool_name so the executor asks the user. "
        'Return only JSON shaped as {"steps":[{"title":str,"description":str|null,'
        '"tool_name":str|null,"arguments":object}]}.\n\n'
        f"TASK TITLE: {task.title}\nTASK DESCRIPTION: {task.description or ''}\n"
        f"MODULE: {task.module_name or 'general'}\n"
        f"REGISTERED TOOLS: {json.dumps(tools, ensure_ascii=False)}\n"
        f"RELEVANT LONG-TERM MEMORY:\n" + ("\n---\n".join(memories) if memories else "(none)")
    )


async def decompose_task(
    db: Session,
    task: Task,
    ai_client: AIClient,
    *,
    max_attempts: int = 3,
    sleep: Callable[[float], Awaitable[None]] = asyncio.sleep,
) -> list[Step]:
    """Plan a task, retry transient/malformed responses, and log every call."""

    if max_attempts < 1:
        raise ValueError("max_attempts must be at least 1")
    memory_results = search_memory(db, f"{task.title} {task.description or ''}", limit=5)
    prompt = _build_prompt(task, [item.entry.content for item in memory_results])
    last_error: Exception | None = None

    for attempt in range(1, max_attempts + 1):
        log = AILog(
            task_id=task.id,
            operation="decompose_task",
            model=getattr(ai_client, "model", AI_MODEL),
            prompt=prompt,
            attempt=attempt,
        )
        db.add(log)
        try:
            raw_response = await ai_client.generate(prompt)
            log.response = (
                raw_response
                if isinstance(raw_response, str)
                else json.dumps(raw_response, ensure_ascii=False)
            )
            plan = parse_plan_response(raw_response)
            db.commit()  # persist the successful AI call before materializing its plan

            # Replanning is allowed only while no existing step has started.
            if any(step.status not in {"pending"} for step in task.steps):
                raise PlanningError("Cannot replace a plan after execution has started")
            db.execute(delete(Step).where(Step.task_id == task.id))
            steps = [
                Step(
                    task_id=task.id,
                    title=item["title"],
                    description=item["description"],
                    position=index,
                    status="pending",
                    tool_name=item["tool_name"],
                    arguments=item["arguments"],
                )
                for index, item in enumerate(plan)
            ]
            db.add_all(steps)
            task.status = "planned"
            db.commit()
            for step in steps:
                db.refresh(step)
            return steps
        except Exception as exc:
            last_error = exc
            if log.id is None or log.response is None:
                log.error = str(exc) or exc.__class__.__name__
                db.commit()
            # Parsing errors also retry: models occasionally wrap or truncate JSON.
            if attempt < max_attempts:
                await sleep(0.25 * (2 ** (attempt - 1)))

    raise PlanningError(
        f"Planning failed after {max_attempts} attempts: {last_error}"
    ) from last_error
