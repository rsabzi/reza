"""Assistant function tools — composition layer.

This module is the orchestration layer between the conversational agent and the
domain modules (salon, personal, memory, scheduler, telegram). It contains no
module-specific business logic itself; every implementation delegates to the
owning module service.
"""

from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from typing import Any

from sqlalchemy import delete, func, select
from sqlalchemy.orm import Session

from ..memory.store import create_playbook_with_chunks
from ..memory.store import search_memory as search_memory_store
from ..models import (
    ContactEndpoint,
    MemoryEntry,
    OutboundMessage,
    Playbook,
    Step,
    Task,
    Tool,
    utcnow,
)
from ..modules.personal.models import PersonalProject
from ..modules.personal.service import (
    REMINDER_WINDOW_DAYS,
    daily_personal_reminder,
    validate_status_transition,
)
from ..modules.salon.models import Salon, SalonInteraction
from ..modules.salon.service import daily_salon_plan, log_interaction
from ..scheduler import materialize_recurring_task
from ..services.permissions import get_tool_record, sync_registered_tools
from ..services.preferences import resolved_reminder_window_days, set_preference
from ..services.telegram import telegram_send_message
from ..tools.registry import ToolContext, register_tool
from .timeparse import parse_clock, parse_relative_date

ASSISTANT_MODULE = "assistant"


def _mobile(value: Any) -> str | None:
    return value.isoformat() if isinstance(value, (date, datetime)) else None


def _task_summary(task: Task) -> dict[str, Any]:
    return {
        "id": task.id,
        "title": task.title,
        "status": task.status,
        "module_name": task.module_name,
        "recurrence_rule": task.recurrence_rule,
        "scheduled_time": task.scheduled_time,
        "description": (task.description or "")[:300],
    }


def _salon_summary(salon: Salon) -> dict[str, Any]:
    return {
        "id": salon.id,
        "name": salon.name,
        "phone": salon.phone,
        "city": salon.city,
        "status": salon.status,
        "last_contact_at": _mobile(salon.last_contact_at),
    }


def _project_summary(project: PersonalProject) -> dict[str, Any]:
    return {
        "id": project.id,
        "title": project.title,
        "client_name": project.client_name,
        "status": project.status,
        "due_date": _mobile(project.due_date),
        "budget": str(project.budget) if project.budget is not None else None,
        "next_action": project.next_action,
    }


def _memory_summary(entry: MemoryEntry) -> dict[str, Any]:
    return {
        "id": entry.id,
        "content": entry.content[:400],
        "source": entry.source,
        "module_name": entry.module_name,
        "created_at": _mobile(entry.created_at),
    }


def _resource(db: Session, resource_type: str, resource_id: int) -> Any:
    resource_type = (resource_type or "").strip().lower()
    model: Any = {
        "task": Task,
        "salon": Salon,
        "project": PersonalProject,
        "memory": MemoryEntry,
        "playbook": Playbook,
        "contact_endpoint": ContactEndpoint,
        "outbound_message": OutboundMessage,
    }.get(resource_type)
    if model is None:
        raise ValueError(
            "Unsupported resource_type; use one of: task, salon, project, memory, "
            "playbook, contact_endpoint, outbound_message"
        )
    return db.get(model, resource_id)


def _resource_summary(db: Session, resource_type: str, resource_id: int) -> dict[str, Any]:
    resource = _resource(db, resource_type, resource_id)
    if resource is None:
        raise ValueError(f"{resource_type} with id {resource_id} was not found")
    if resource_type == "task":
        return {
            "resource_type": "task",
            "resource_id": resource_id,
            "item": _task_summary(resource),
        }
    if resource_type == "salon":
        return {
            "resource_type": "salon",
            "resource_id": resource_id,
            "item": _salon_summary(resource),
        }
    if resource_type == "project":
        return {
            "resource_type": "project",
            "resource_id": resource_id,
            "item": _project_summary(resource),
        }
    if resource_type == "memory":
        return {
            "resource_type": "memory",
            "resource_id": resource_id,
            "item": _memory_summary(resource),
        }
    if resource_type == "playbook":
        return {
            "resource_type": "playbook",
            "resource_id": resource_id,
            "item": {
                "id": resource.id,
                "title": resource.title,
                "module_name": resource.module_name,
            },
        }
    if resource_type == "contact_endpoint":
        return {
            "resource_type": "contact_endpoint",
            "resource_id": resource_id,
            "item": {
                "id": resource.id,
                "owner_type": resource.owner_type,
                "owner_id": resource.owner_id,
                "channel": resource.channel,
                "address": resource.address,
                "label": resource.label,
                "enabled": resource.enabled,
            },
        }
    return {
        "resource_type": resource_type,
        "resource_id": resource_id,
        "item": {
            "id": resource.id,
            "status": resource.status,
            "provider_message_id": resource.provider_message_id,
            "sent_at": _mobile(resource.sent_at),
        },
    }


def _delete_resource(db: Session, resource_type: str, resource_id: int) -> dict[str, Any]:
    resource = _resource(db, resource_type, resource_id)
    if resource is None:
        raise ValueError(f"{resource_type} with id {resource_id} was not found")
    if resource_type == "playbook":
        db.execute(
            delete(MemoryEntry).where(
                MemoryEntry.source == "playbook", MemoryEntry.source_id == str(resource_id)
            )
        )
    db.delete(resource)
    db.commit()
    return {"deleted": True, "resource_type": resource_type, "resource_id": resource_id}


# ---------------------------------------------------------------------------
# Read actions
# ---------------------------------------------------------------------------


@register_tool(
    "get_current_state",
    "Compact snapshot of current state: active tasks, open approvals, today's salon plan, "
    "near-due projects and recent memory.",
    requires_approval=False,
)
def get_current_state(context: ToolContext) -> dict[str, Any]:
    db = context.db
    active_tasks = list(
        db.scalars(
            select(Task)
            .where(
                Task.status == "pending",
                (Task.module_name.is_(None)) | (Task.module_name != ASSISTANT_MODULE),
            )
            .order_by(Task.created_at.desc())
            .limit(8)
        )
    )
    pending_approvals = list(
        db.scalars(
            select(Step)
            .where(Step.status == "needs_approval")
            .order_by(Step.created_at.desc())
            .limit(10)
        )
    )
    approvals = [
        {
            "step_id": step.id,
            "tool_name": step.tool_name,
            "arguments": step.arguments,
            "title": step.title,
        }
        for step in pending_approvals
    ]
    salons = daily_salon_plan(db)
    projects = daily_personal_reminder(
        db, within_days=resolved_reminder_window_days(db, REMINDER_WINDOW_DAYS)
    )
    recent_memory = list(
        db.scalars(select(MemoryEntry).order_by(MemoryEntry.created_at.desc()).limit(3))
    )
    return {
        "date": utcnow().isoformat(),
        "active_tasks": [_task_summary(item) for item in active_tasks],
        "pending_approvals": approvals,
        "daily_salon_plan": [
            {"id": item["salon"].id, "name": item["salon"].name, "reason": item["reason"]}
            for item in salons[:6]
        ],
        "due_projects": [
            {
                "id": item["project"].id,
                "title": item["project"].title,
                "days_until_due": item["days_until_due"],
            }
            for item in projects[:6]
        ],
        "recent_memory": [_memory_summary(item) for item in recent_memory],
    }


@register_tool(
    "get_task_details",
    "Retrieve full task details including execution steps.",
    requires_approval=False,
    schema={
        "type": "object",
        "properties": {"task_id": {"type": "integer"}},
        "required": ["task_id"],
    },
)
def get_task_details(context: ToolContext, task_id: int) -> dict[str, Any]:
    task = context.db.get(Task, task_id)
    if task is None:
        raise ValueError(f"Task with id {task_id} was not found")
    steps = list(
        context.db.scalars(select(Step).where(Step.task_id == task.id).order_by(Step.position))
    )
    return {
        "task": _task_summary(task),
        "steps": [
            {
                "id": step.id,
                "title": step.title,
                "status": step.status,
                "tool_name": step.tool_name,
                "arguments": step.arguments,
                "result": step.result,
                "error": step.error,
            }
            for step in steps
        ],
    }


@register_tool(
    "list_due_tasks",
    "List tasks by status (assistant-internal tasks are excluded).",
    requires_approval=False,
)
def list_due_tasks(
    context: ToolContext, status: str = "pending", limit: int = 10
) -> dict[str, Any]:
    if status not in {"pending", "planned", "running", "paused", "done", "failed", "cancelled"}:
        raise ValueError(f"Invalid status '{status}'")
    limit = max(1, min(int(limit), 50))
    tasks = list(
        context.db.scalars(
            select(Task)
            .where(
                Task.status == status,
                (Task.module_name.is_(None)) | (Task.module_name != ASSISTANT_MODULE),
            )
            .order_by(Task.created_at.desc())
            .limit(limit),
        )
    )
    return {"count": len(tasks), "tasks": [_task_summary(item) for item in tasks]}


@register_tool(
    "get_salon_details",
    "Retrieve full salon details including recent interactions.",
    requires_approval=False,
    schema={
        "type": "object",
        "properties": {"salon_id": {"type": "integer"}},
        "required": ["salon_id"],
    },
)
def get_salon_details(context: ToolContext, salon_id: int) -> dict[str, Any]:
    salon = context.db.get(Salon, salon_id)
    if salon is None:
        raise ValueError(f"Salon with id {salon_id} was not found")
    items = list(
        context.db.scalars(
            select(SalonInteraction)
            .where(SalonInteraction.salon_id == salon.id)
            .order_by(SalonInteraction.occurred_at.desc())
            .limit(10),
        )
    )
    return {
        "salon": _salon_summary(salon),
        "recent_interactions": [
            {
                "id": item.id,
                "channel": item.channel,
                "direction": item.direction,
                "content": item.content[:300],
                "outcome": item.outcome,
                "occurred_at": _mobile(item.occurred_at),
            }
            for item in items
        ],
    }


@register_tool(
    "get_daily_salon_plan",
    "List salons eligible for contact today under the current playbook cadence.",
    requires_approval=False,
)
def get_daily_salon_plan_tool(context: ToolContext) -> dict[str, Any]:
    plan = daily_salon_plan(context.db)
    return {
        "count": len(plan),
        "salons": [
            {"id": item["salon"].id, "name": item["salon"].name, "reason": item["reason"]}
            for item in plan
        ],
    }


@register_tool(
    "get_project_details",
    "Retrieve full personal/freelance project details.",
    requires_approval=False,
    schema={
        "type": "object",
        "properties": {"project_id": {"type": "integer"}},
        "required": ["project_id"],
    },
)
def get_project_details(context: ToolContext, project_id: int) -> dict[str, Any]:
    project = context.db.get(PersonalProject, project_id)
    if project is None:
        raise ValueError(f"Personal project with id {project_id} was not found")
    return {"project": _project_summary(project)}


@register_tool(
    "get_personal_reminders",
    "List personal projects with near due dates.",
    requires_approval=False,
)
def get_personal_reminders_tool(
    context: ToolContext, within_days: int | None = None
) -> dict[str, Any]:
    effective = (
        within_days
        if within_days is not None
        else resolved_reminder_window_days(context.db, REMINDER_WINDOW_DAYS)
    )
    window = max(0, min(int(effective), 365))
    reminders = daily_personal_reminder(context.db, within_days=window)
    return {
        "window_days": window,
        "count": len(reminders),
        "projects": [
            {
                "id": item["project"].id,
                "title": item["project"].title,
                "days_until_due": item["days_until_due"],
            }
            for item in reminders
        ],
    }


@register_tool(
    "search_memory",
    "Semantic search over long-term memory and playbooks.",
    requires_approval=False,
    schema={
        "type": "object",
        "properties": {
            "query": {"type": "string"},
            "limit": {"type": "integer"},
        },
        "required": ["query"],
    },
)
def search_memory_tool(context: ToolContext, query: str, limit: int = 5) -> dict[str, Any]:
    if not query.strip():
        raise ValueError("query must not be blank")
    limit = max(1, min(int(limit), 10))
    results = search_memory_store(context.db, query.strip(), limit=limit)
    return {
        "count": len(results),
        "results": [
            {**_memory_summary(item.entry), "score": round(item.score, 4)} for item in results
        ],
    }


@register_tool(
    "list_tools_and_policies",
    "List registered tools with their enabled / requires-approval policy flags.",
    requires_approval=False,
)
def list_tools_and_policies(context: ToolContext) -> dict[str, Any]:
    sync_registered_tools(context.db)
    tools = list(context.db.scalars(select(Tool).order_by(Tool.name)))
    return {
        "count": len(tools),
        "tools": [
            {
                "name": item.name,
                "description": item.description[:200],
                "enabled": item.enabled,
                "requires_approval": item.requires_approval,
            }
            for item in tools
        ],
    }


# ---------------------------------------------------------------------------
# Task actions
# ---------------------------------------------------------------------------


@register_tool(
    "create_task",
    "Create a task; for daily recurring tasks pass recurrence_rule='daily' and a clock time.",
    requires_approval=False,
    schema={
        "type": "object",
        "properties": {
            "title": {"type": "string"},
            "description": {"type": "string"},
            "module_name": {"type": "string"},
            "recurrence_rule": {"type": "string", "enum": ["daily"]},
            "scheduled_time": {
                "type": "string",
                "description": "HH:MM like 09:00 or Persian text like 'ساعت ۹ صبح'",
            },
        },
        "required": ["title"],
    },
)
def create_task(
    context: ToolContext,
    title: str,
    description: str | None = None,
    module_name: str | None = None,
    recurrence_rule: str | None = None,
    scheduled_time: str | None = None,
) -> dict[str, Any]:
    title = title.strip()
    if not title:
        raise ValueError("title must not be blank")
    if recurrence_rule == "daily" and not scheduled_time:
        raise ValueError("scheduled_time (HH:MM) is required for daily tasks")
    clock = parse_clock(scheduled_time)
    task = Task(
        title=title[:255],
        description=description,
        status="pending",
        module_name=module_name,
        recurrence_rule=recurrence_rule,
        scheduled_time=clock,
    )
    context.db.add(task)
    context.db.commit()
    context.db.refresh(task)
    return {"task_id": task.id, "task": _task_summary(task)}


@register_tool(
    "update_task",
    "Update task fields; only provided fields change.",
    requires_approval=False,
)
def update_task(
    context: ToolContext,
    task_id: int,
    title: str | None = None,
    description: str | None = None,
    status: str | None = None,
    module_name: str | None = None,
    recurrence_rule: str | None = None,
    scheduled_time: str | None = None,
) -> dict[str, Any]:
    task = context.db.get(Task, task_id)
    if task is None:
        raise ValueError(f"Task with id {task_id} was not found")
    values: dict[str, Any] = {}
    if title is not None:
        if not title.strip():
            raise ValueError("title must not be blank")
        values["title"] = title.strip()
    if status is not None:
        if status not in {"pending", "planned", "running", "paused", "done", "failed", "cancelled"}:
            raise ValueError(f"Invalid status '{status}'")
        values["status"] = status
    if description is not None:
        values["description"] = description
    if module_name is not None:
        values["module_name"] = module_name
    if recurrence_rule is not None:
        values["recurrence_rule"] = recurrence_rule
    if scheduled_time is not None:
        values["scheduled_time"] = parse_clock(scheduled_time)
    for field, value in values.items():
        setattr(task, field, value)
    if task.recurrence_rule and not task.scheduled_time:
        raise ValueError("daily tasks require scheduled_time (HH:MM)")
    context.db.commit()
    context.db.refresh(task)
    return {"task_id": task.id, "task": _task_summary(task)}


@register_tool(
    "schedule_task",
    "Schedule a task; optional daily recurrence.",
    requires_approval=False,
)
def schedule_task(
    context: ToolContext,
    task_id: int,
    scheduled_time: str,
    recurrence: bool = False,
) -> dict[str, Any]:
    task = context.db.get(Task, task_id)
    if task is None:
        raise ValueError(f"Task with id {task_id} was not found")
    clock = parse_clock(scheduled_time)
    if clock is None:
        raise ValueError("Could not parse time; provide HH:MM like 09:00")
    task.scheduled_time = clock
    task.recurrence_rule = "daily" if recurrence else None
    context.db.commit()
    context.db.refresh(task)
    return {"task_id": task.id, "scheduled_time": clock, "recurrence_rule": task.recurrence_rule}


@register_tool(
    "add_task_step",
    "Add an execution step to a task plan.",
    requires_approval=False,
)
def add_task_step(
    context: ToolContext,
    task_id: int,
    title: str,
    tool_name: str | None = None,
    arguments: dict[str, Any] | None = None,
) -> dict[str, Any]:
    task = context.db.get(Task, task_id)
    if task is None:
        raise ValueError(f"Task with id {task_id} was not found")
    if tool_name:
        get_tool_record(context.db, tool_name)
    highest = context.db.scalar(select(func.max(Step.position)).where(Step.task_id == task.id))
    position = int(highest) + 1 if highest is not None else 0
    step = Step(
        task_id=task.id,
        title=title[:255],
        position=position,
        status="pending",
        tool_name=tool_name,
        arguments=arguments or {},
    )
    context.db.add(step)
    if task.status in {"done", "cancelled", "failed"}:
        task.status = "pending"
    context.db.commit()
    context.db.refresh(step)
    return {"task_id": task.id, "step_id": step.id, "position": step.position}


@register_tool(
    "run_task",
    "Execute a task plan; pauses at approval gates.",
    requires_approval=False,
)
async def run_task(context: ToolContext, task_id: int) -> dict[str, Any]:
    from ..agent.executor import execute_task

    task = context.db.get(Task, task_id)
    if task is None:
        raise ValueError(f"Task with id {task_id} was not found")
    instance = task
    if task.recurrence_rule == "daily" and task.scheduled_time:
        instance = materialize_recurring_task(context.db, task)
        context.db.refresh(instance)
    result = await execute_task(context.db, instance.id)
    done = context.db.scalar(
        select(func.count(Step.id)).where(Step.task_id == instance.id, Step.status == "done")
    )
    total = context.db.scalar(select(func.count(Step.id)).where(Step.task_id == instance.id))
    return {
        "task_id": instance.id,
        "status": result.status,
        "steps_done": int(done or 0),
        "steps_total": int(total or 0),
    }


@register_tool(
    "prepare_delete",
    "Validate a deletion without deleting anything; returns a summary.",
    requires_approval=False,
)
def prepare_delete(context: ToolContext, resource_type: str, resource_id: int) -> dict[str, Any]:
    summary = _resource_summary(context.db, resource_type, resource_id)
    return {"requires_approval": True, "will_delete": summary}


@register_tool(
    "delete_application_record",
    "Really delete a record; always requires user approval and runs exactly once.",
    requires_approval=True,
)
def delete_application_record(
    context: ToolContext, resource_type: str, resource_id: int
) -> dict[str, Any]:
    return _delete_resource(context.db, resource_type, resource_id)


# ---------------------------------------------------------------------------
# Salon actions
# ---------------------------------------------------------------------------


@register_tool(
    "create_salon",
    "Add a salon to the CRM; phone must be unique.",
    requires_approval=False,
)
def create_salon(
    context: ToolContext,
    name: str,
    phone: str,
    city: str | None = None,
    address: str | None = None,
    status: str = "lead",
    notes: str | None = None,
    tags: list[str] | None = None,
) -> dict[str, Any]:
    name = name.strip()
    phone = phone.strip()
    if not name:
        raise ValueError("name must not be blank")
    if not phone:
        raise ValueError("phone must not be blank")
    if status not in {"lead", "contacted", "interested", "customer", "inactive", "do_not_contact"}:
        raise ValueError(f"Invalid salon status '{status}'")
    exists = context.db.scalar(select(Salon.id).where(Salon.phone == phone))
    if exists is not None:
        raise ValueError(f"A salon with phone {phone} already exists (id={exists})")
    salon = Salon(
        name=name,
        phone=phone,
        city=city,
        address=address,
        status=status,
        notes=notes,
        tags=tags or [],
    )
    context.db.add(salon)
    context.db.commit()
    context.db.refresh(salon)
    return {"salon_id": salon.id, "salon": _salon_summary(salon)}


@register_tool(
    "update_salon",
    "Update salon fields; only provided fields change.",
    requires_approval=False,
)
def update_salon(
    context: ToolContext,
    salon_id: int,
    name: str | None = None,
    phone: str | None = None,
    city: str | None = None,
    address: str | None = None,
    status: str | None = None,
    notes: str | None = None,
    tags: list[str] | None = None,
) -> dict[str, Any]:
    salon = context.db.get(Salon, salon_id)
    if salon is None:
        raise ValueError(f"Salon with id {salon_id} was not found")
    if name is not None:
        if not name.strip():
            raise ValueError("name must not be blank")
        salon.name = name.strip()
    if phone is not None:
        salon.phone = phone.strip()
        exists = context.db.scalar(
            select(Salon.id).where(Salon.phone == salon.phone, Salon.id != salon.id)
        )
        if exists is not None:
            raise ValueError(f"A salon with phone {salon.phone} already exists")
    if city is not None:
        salon.city = city
    if address is not None:
        salon.address = address
    if status is not None:
        if status not in {
            "lead",
            "contacted",
            "interested",
            "customer",
            "inactive",
            "do_not_contact",
        }:
            raise ValueError(f"Invalid salon status '{status}'")
        salon.status = status
    if notes is not None:
        salon.notes = notes
    if tags is not None:
        salon.tags = tags
    context.db.commit()
    context.db.refresh(salon)
    return {"salon_id": salon.id, "salon": _salon_summary(salon)}


@register_tool(
    "log_salon_interaction",
    "Record a salon interaction and save it to long-term memory.",
    requires_approval=False,
)
def log_salon_interaction_tool(
    context: ToolContext,
    salon_id: int,
    channel: str,
    content: str,
    direction: str = "outbound",
    outcome: str | None = None,
) -> dict[str, Any]:
    salon = context.db.get(Salon, salon_id)
    if salon is None:
        raise ValueError(f"Salon with id {salon_id} was not found")
    if not content.strip():
        raise ValueError("content must not be blank")
    interaction = log_interaction(
        context.db,
        salon=salon,
        channel=channel,
        direction=direction,
        content=content,
        outcome=outcome,
        commit=False,
    )
    context.db.commit()
    return {"interaction_id": interaction.id, "salon_id": salon.id, "status": "logged"}


@register_tool(
    "prepare_salon_outreach",
    "Draft a personalized Persian outreach message for a salon; external use needs approval.",
    requires_approval=True,
)
def prepare_salon_outreach(
    context: ToolContext, salon_id: int, offer: str = "خدمات رشد و بازاریابی"
) -> dict[str, Any]:
    salon = context.db.get(Salon, salon_id)
    if salon is None:
        raise ValueError(f"Salon with id {salon_id} was not found")
    city_text = f" در {salon.city}" if salon.city else ""
    script = (
        f"سلام {salon.name} عزیز، وقت‌تان بخیر. ما برای سالن‌های زیبایی{city_text} "
        f"روی {offer} کار می‌کنیم. خوشحال می‌شویم در یک گفت‌وگوی کوتاه نیازهای شما را بشنویم."
    )
    return {"salon_id": salon.id, "content": script, "status": "ready_for_approval"}


# ---------------------------------------------------------------------------
# Personal / freelance actions
# ---------------------------------------------------------------------------


def _resolve_date(value: str | None) -> date | None:
    if not value:
        return None
    resolved = parse_relative_date(value)
    if resolved is not None:
        return resolved
    try:
        return date.fromisoformat(value.strip())
    except ValueError as exc:
        raise ValueError("due_date must be YYYY-MM-DD or a weekday name") from exc


@register_tool(
    "create_personal_project",
    "Create a personal/freelance project; due_date may be YYYY-MM-DD or a weekday name.",
    requires_approval=False,
)
def create_personal_project(
    context: ToolContext,
    title: str,
    client_name: str | None = None,
    description: str | None = None,
    status: str = "lead",
    due_date: str | None = None,
    budget: float | None = None,
    next_action: str | None = None,
    external_url: str | None = None,
) -> dict[str, Any]:
    title = title.strip()
    if not title:
        raise ValueError("title must not be blank")
    if status not in {"lead", "active", "submitted", "won", "lost", "completed", "paused"}:
        raise ValueError(f"Invalid project status '{status}'")
    project = PersonalProject(
        title=title,
        client_name=client_name,
        description=description,
        status=status,
        due_date=_resolve_date(due_date),
        budget=None if budget is None else Decimal(str(budget)),
        next_action=next_action,
        external_url=external_url,
    )
    context.db.add(project)
    context.db.commit()
    context.db.refresh(project)
    return {"project_id": project.id, "project": _project_summary(project)}


@register_tool(
    "update_personal_project",
    "Update a personal project with valid status transitions.",
    requires_approval=False,
)
def update_personal_project(
    context: ToolContext,
    project_id: int,
    title: str | None = None,
    client_name: str | None = None,
    description: str | None = None,
    status: str | None = None,
    due_date: str | None = None,
    budget: float | None = None,
    next_action: str | None = None,
    external_url: str | None = None,
) -> dict[str, Any]:
    project = context.db.get(PersonalProject, project_id)
    if project is None:
        raise ValueError(f"Personal project with id {project_id} was not found")
    if status is not None:
        validate_status_transition(project.status, status)
        project.status = status
    if title is not None:
        if not title.strip():
            raise ValueError("title must not be blank")
        project.title = title.strip()
    if client_name is not None:
        project.client_name = client_name
    if description is not None:
        project.description = description
    if due_date is not None:
        project.due_date = _resolve_date(due_date)
    if budget is not None:
        project.budget = Decimal(str(budget))
    if next_action is not None:
        project.next_action = next_action
    if external_url is not None:
        project.external_url = external_url
    context.db.commit()
    context.db.refresh(project)
    return {"project_id": project.id, "project": _project_summary(project)}


@register_tool(
    "prepare_project_proposal",
    "Draft a professional freelance proposal; external use needs approval.",
    requires_approval=True,
)
def prepare_project_proposal(
    context: ToolContext, project_id: int, approach: str | None = None
) -> dict[str, Any]:
    project = context.db.get(PersonalProject, project_id)
    if project is None:
        raise ValueError(f"Personal project with id {project_id} was not found")
    client = project.client_name or "کارفرمای محترم"
    approach_text = approach or project.next_action or "تحویل مرحله‌ای، شفاف و قابل‌اندازه‌گیری"
    proposal = (
        f"سلام {client}،\n\n"
        f"برای پروژه «{project.title}» پیشنهاد می‌کنم با رویکرد {approach_text} پیش برویم. "
        "پس از تأیید محدوده، زمان‌بندی و خروجی هر مرحله را دقیق ثبت می‌کنم.\n\n"
        "با احترام"
    )
    return {"project_id": project.id, "proposal": proposal, "status": "ready_for_approval"}


# ---------------------------------------------------------------------------
# Memory / playbook actions
# ---------------------------------------------------------------------------


@register_tool(
    "create_playbook",
    "Create a playbook and index it into memory automatically.",
    requires_approval=False,
)
def create_playbook_tool(
    context: ToolContext,
    title: str,
    content: str,
    module_name: str | None = None,
    chunk_size: int = 800,
) -> dict[str, Any]:
    if not title.strip():
        raise ValueError("title must not be blank")
    if not content.strip():
        raise ValueError("content must not be blank")
    book = create_playbook_with_chunks(
        context.db,
        title=title.strip(),
        content=content,
        module_name=module_name,
        chunk_size=max(100, min(int(chunk_size), 5000)),
    )
    return {"playbook_id": book.id, "title": book.title, "module_name": book.module_name}


@register_tool(
    "summarize_recent_results",
    "Return recent completed task results from memory for summarization.",
    requires_approval=False,
)
def summarize_recent_results(context: ToolContext, limit: int = 10) -> dict[str, Any]:
    limit = max(1, min(int(limit), 30))
    entries = list(
        context.db.scalars(
            select(MemoryEntry)
            .where(MemoryEntry.source == "task_result")
            .order_by(MemoryEntry.created_at.desc())
            .limit(limit),
        )
    )
    return {"count": len(entries), "results": [_memory_summary(item) for item in entries]}


# ---------------------------------------------------------------------------
# Settings actions
# ---------------------------------------------------------------------------


@register_tool(
    "set_tool_policy",
    "Enable/disable a tool or change its requires-approval policy.",
    requires_approval=False,
)
def set_tool_policy(
    context: ToolContext,
    tool_name: str,
    enabled: bool | None = None,
    requires_approval: bool | None = None,
) -> dict[str, Any]:
    _, record = get_tool_record(context.db, tool_name)
    changed: dict[str, Any] = {}
    if enabled is not None:
        record.enabled = bool(enabled)
        changed["enabled"] = record.enabled
    if requires_approval is not None:
        record.requires_approval = bool(requires_approval)
        changed["requires_approval"] = record.requires_approval
    if not changed:
        raise ValueError("Provide enabled and/or requires_approval")
    context.db.commit()
    context.db.refresh(record)
    return {
        "tool_name": record.name,
        "enabled": record.enabled,
        "requires_approval": record.requires_approval,
        "changed": changed,
    }


@register_tool(
    "set_default_reminder_window",
    "Set the default personal-project reminder window in days (0-365).",
    requires_approval=False,
)
def set_default_reminder_window(context: ToolContext, days: int) -> dict[str, Any]:
    if not 0 <= days <= 365:
        raise ValueError("days must be between 0 and 365")
    set_preference(context.db, "reminder_window_days", str(days))
    return {"reminder_window_days": days}


@register_tool(
    "set_model_preference",
    "Choose the Gemini model for conversations and planning.",
    requires_approval=False,
)
def set_model_preference(context: ToolContext, model: str) -> dict[str, Any]:
    from ..agent.ai_client import SUPPORTED_MODEL_CANDIDATES

    if model not in SUPPORTED_MODEL_CANDIDATES:
        raise ValueError(
            f"Unsupported model '{model}'; supported: {', '.join(SUPPORTED_MODEL_CANDIDATES)}"
        )
    set_preference(context.db, "gemini_model", model)
    return {"model": model, "status": "preferred"}


# ---------------------------------------------------------------------------
# Outbound messaging
# ---------------------------------------------------------------------------


@register_tool(
    "send_telegram_message",
    "Send a real Telegram message through the connected bot; requires approval and only "
    "reports 'sent' after a provider receipt.",
    requires_approval=True,
)
async def send_telegram_message_tool(
    context: ToolContext,
    content: str,
    owner_type: str = "general",
    owner_id: int | None = None,
    contact_endpoint_id: int | None = None,
) -> dict[str, Any]:
    if not content.strip():
        raise ValueError("content must not be blank")
    if owner_type not in {"salon", "project", "general"}:
        raise ValueError("owner_type must be salon, project or general")
    call_id = context.call_id or f"manual-{utcnow().timestamp()}"

    endpoint = None
    if contact_endpoint_id is not None:
        endpoint = context.db.get(ContactEndpoint, contact_endpoint_id)
        if endpoint is None or not endpoint.enabled or endpoint.channel != "telegram":
            raise ValueError("The selected contact endpoint does not exist or is not enabled")
    if endpoint is None:
        query = select(ContactEndpoint).where(
            ContactEndpoint.channel == "telegram", ContactEndpoint.enabled.is_(True)
        )
        if owner_type != "general" and owner_id is not None:
            query = query.where(
                ContactEndpoint.owner_type == owner_type, ContactEndpoint.owner_id == owner_id
            )
        endpoint = context.db.scalar(query.order_by(ContactEndpoint.id))
    if endpoint is None:
        raise ValueError(
            "No enabled Telegram contact chat_id is configured for this owner; "
            "recipient must be added in Settings before sending"
        )

    message = context.db.scalar(
        select(OutboundMessage).where(OutboundMessage.idempotency_key == call_id)
    )
    if message is None:
        message = OutboundMessage(
            owner_type=owner_type,
            owner_id=owner_id,
            contact_endpoint_id=endpoint.id,
            channel="telegram",
            content=content.strip(),
            status="needs_approval",
            idempotency_key=call_id,
        )
        context.db.add(message)
        context.db.commit()
        context.db.refresh(message)

    if message.provider_message_id and message.status == "sent":
        return {
            "message_id": message.id,
            "status": "sent",
            "provider_message_id": message.provider_message_id,
            "receipt": message.provider_response,
        }

    message.status = "sending"
    message.contact_endpoint_id = endpoint.id
    message.error = None
    context.db.flush()
    try:
        provider_message_id, receipt = await telegram_send_message(
            context.db,
            chat_id=endpoint.address,
            text=message.content,
        )
    except Exception as exc:
        context.db.rollback()
        failed = context.db.get(OutboundMessage, message.id)
        if failed is not None:
            failed.status = "failed"
            failed.error = str(exc)[:2000]
            context.db.commit()
        raise ValueError(f"Telegram send failed: {exc}") from exc

    message = context.db.get(OutboundMessage, message.id)
    message.provider_message_id = provider_message_id
    message.provider_response = receipt
    message.status = "sent"
    message.sent_at = utcnow()
    message.error = None
    context.db.commit()

    if owner_type == "salon" and owner_id is not None:
        salon = context.db.get(Salon, owner_id)
        if salon is not None:
            log_interaction(
                context.db,
                salon=salon,
                channel="telegram",
                direction="outbound",
                content=message.content,
                outcome=f"sent: {provider_message_id}",
                commit=False,
            )
            context.db.commit()
    return {
        "message_id": message.id,
        "status": "sent",
        "provider_message_id": provider_message_id,
        "receipt": {"ok": True, "message_id": provider_message_id},
    }


def queue_outbound_message(
    db: Session,
    *,
    provider_call_id: str,
    content: str,
    owner_type: str,
    owner_id: int | None,
    contact_endpoint_id: int | None,
) -> OutboundMessage:
    """Create the needs-approval OutboundMessage before any provider call happens."""

    existing = db.scalar(
        select(OutboundMessage).where(OutboundMessage.idempotency_key == provider_call_id)
    )
    if existing is not None:
        return existing
    message = OutboundMessage(
        owner_type=owner_type,
        owner_id=owner_id,
        contact_endpoint_id=contact_endpoint_id,
        channel="telegram",
        content=content.strip(),
        status="needs_approval",
        idempotency_key=provider_call_id,
    )
    db.add(message)
    db.commit()
    db.refresh(message)
    return message
