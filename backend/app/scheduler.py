"""APScheduler integration and deterministic recurring-task materialization."""

from __future__ import annotations

import os
from datetime import datetime, timezone
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from apscheduler.schedulers.background import BackgroundScheduler
from sqlalchemy import select
from sqlalchemy.orm import Session

from .database import SessionLocal
from .models import Step, Task, utcnow

_scheduler: BackgroundScheduler | None = None


def agent_timezone() -> ZoneInfo:
    name = os.getenv("AGENT_TIMEZONE", "UTC")
    try:
        return ZoneInfo(name)
    except ZoneInfoNotFoundError as exc:
        raise ValueError(f"Unknown AGENT_TIMEZONE: {name}") from exc


def _aware_utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


def materialize_recurring_task(
    db: Session,
    template: Task,
    *,
    triggered_at: datetime | None = None,
) -> Task:
    """Clone a recurring task and its plan into a one-off pending instance."""

    if template.recurrence_rule != "daily" or not template.scheduled_time:
        raise ValueError("Task is not a configured daily recurrence template")
    instance = Task(
        title=template.title,
        description=template.description,
        status="pending",
        module_name=template.module_name,
        parent_task_id=template.id,
        recurrence_rule=None,
        scheduled_time=None,
    )
    db.add(instance)
    db.flush()
    source_steps = list(
        db.scalars(select(Step).where(Step.task_id == template.id).order_by(Step.position))
    )
    db.add_all(
        [
            Step(
                task_id=instance.id,
                title=source.title,
                description=source.description,
                position=source.position,
                status="pending",
                tool_name=source.tool_name,
                arguments=dict(source.arguments or {}),
                requires_approval=False,
            )
            for source in source_steps
        ]
    )
    template.last_scheduled_at = _aware_utc(triggered_at or utcnow())
    db.commit()
    db.refresh(instance)
    return instance


def process_due_recurring_tasks(db: Session, *, now: datetime | None = None) -> list[Task]:
    """Create instances due at `now`; injectable time makes this fully testable."""

    utc_now = _aware_utc(now or utcnow())
    local_now = utc_now.astimezone(agent_timezone())
    templates = list(
        db.scalars(
            select(Task).where(Task.recurrence_rule == "daily", Task.scheduled_time.is_not(None))
        )
    )
    created: list[Task] = []
    for template in templates:
        hour, minute = (int(part) for part in template.scheduled_time.split(":"))
        scheduled_today = local_now.replace(hour=hour, minute=minute, second=0, microsecond=0)
        if local_now < scheduled_today:
            continue
        if template.last_scheduled_at is not None:
            last_local = _aware_utc(template.last_scheduled_at).astimezone(agent_timezone())
            if last_local.date() >= local_now.date():
                continue
        created.append(materialize_recurring_task(db, template, triggered_at=utc_now))
    return created


def _poll_due_tasks() -> None:
    with SessionLocal() as db:
        process_due_recurring_tasks(db)


def start_scheduler() -> BackgroundScheduler:
    global _scheduler
    if _scheduler is not None and _scheduler.running:
        return _scheduler
    scheduler = BackgroundScheduler(timezone=agent_timezone())
    scheduler.add_job(
        _poll_due_tasks,
        trigger="interval",
        seconds=30,
        id="recurring-task-poller",
        max_instances=1,
        coalesce=True,
        replace_existing=True,
    )
    scheduler.start()
    _scheduler = scheduler
    return scheduler


def stop_scheduler() -> None:
    global _scheduler
    if _scheduler is not None and _scheduler.running:
        _scheduler.shutdown(wait=False)
    _scheduler = None


def scheduler_running() -> bool:
    return bool(_scheduler and _scheduler.running)
