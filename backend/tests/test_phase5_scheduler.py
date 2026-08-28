from __future__ import annotations

from datetime import datetime, timezone

import pytest
from sqlalchemy import select

from backend.app.models import Step, Task
from backend.app.scheduler import (
    materialize_recurring_task,
    process_due_recurring_tasks,
)

pytestmark = pytest.mark.asyncio


def make_template(db) -> Task:
    template = Task(
        title="Daily follow-up",
        description="Run the same workflow",
        module_name="general",
        recurrence_rule="daily",
        scheduled_time="09:00",
    )
    db.add(template)
    db.flush()
    db.add(
        Step(
            task_id=template.id,
            title="Echo reminder",
            position=0,
            tool_name="echo",
            arguments={"value": "daily"},
        )
    )
    db.commit()
    return template


async def test_daily_rule_creates_instance_when_clock_advances(db, monkeypatch):
    monkeypatch.setenv("AGENT_TIMEZONE", "UTC")
    template = make_template(db)

    # Before the injected scheduled time, nothing is created.
    before = process_due_recurring_tasks(db, now=datetime(2026, 8, 27, 8, 59, tzinfo=timezone.utc))
    assert before == []

    due = process_due_recurring_tasks(db, now=datetime(2026, 8, 27, 9, 0, tzinfo=timezone.utc))
    assert len(due) == 1
    assert due[0].parent_task_id == template.id
    assert due[0].recurrence_rule is None
    cloned_steps = list(db.scalars(select(Step).where(Step.task_id == due[0].id)))
    assert len(cloned_steps) == 1
    assert cloned_steps[0].status == "pending"
    assert cloned_steps[0].arguments == {"value": "daily"}

    # Same-day polls are coalesced; next day's injected clock creates another.
    assert (
        process_due_recurring_tasks(db, now=datetime(2026, 8, 27, 18, 0, tzinfo=timezone.utc)) == []
    )
    next_day = process_due_recurring_tasks(db, now=datetime(2026, 8, 28, 9, 1, tzinfo=timezone.utc))
    assert len(next_day) == 1


async def test_run_now_api_matches_scheduled_materialization(client, db, monkeypatch):
    monkeypatch.setenv("AGENT_TIMEZONE", "UTC")
    template = make_template(db)
    manual = await client.post(f"/api/tasks/{template.id}/run-now")
    assert manual.status_code == 201, manual.text

    # Advance to another day so a scheduled instance is due too.
    scheduled = await client.post("/api/scheduler/run-due", json={"now": "2026-08-29T09:00:00Z"})
    assert scheduled.status_code == 201
    assert len(scheduled.json()) == 1

    manual_json = manual.json()
    scheduled_json = scheduled.json()[0]
    for field in ("title", "description", "module_name", "parent_task_id", "status"):
        assert manual_json[field] == scheduled_json[field]
    assert manual_json["recurrence_rule"] is None
    assert scheduled_json["recurrence_rule"] is None


async def test_scheduler_endpoint_errors_and_status(client):
    missing = await client.post("/api/tasks/999999/run-now")
    assert missing.status_code == 404

    ordinary = (await client.post("/api/tasks", json={"title": "Not recurring"})).json()
    conflict = await client.post(f"/api/tasks/{ordinary['id']}/run-now")
    assert conflict.status_code == 409
    assert "not a configured" in conflict.json()["detail"]

    status_response = await client.get("/api/scheduler/status")
    assert status_response.status_code == 200
    assert status_response.json()["poll_interval"] == "30 seconds"


async def test_materializer_rejects_invalid_template(db):
    task = Task(title="Invalid")
    db.add(task)
    db.commit()
    with pytest.raises(ValueError, match="not a configured"):
        materialize_recurring_task(db, task)
