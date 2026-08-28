from __future__ import annotations

from datetime import date, timedelta
from decimal import Decimal

import pytest
from sqlalchemy.exc import IntegrityError

from backend.app.modules.personal.models import PersonalProject
from backend.app.modules.personal.service import daily_personal_reminder

pytestmark = pytest.mark.asyncio


async def test_personal_project_full_crud_and_status_transitions(client):
    created = await client.post(
        "/api/personal/projects",
        json={
            "title": "Build landing page",
            "client_name": "ACME",
            "due_date": "2026-09-01",
            "budget": "1200.50",
        },
    )
    assert created.status_code == 201, created.text
    project_id = created.json()["id"]
    assert created.json()["status"] == "lead"

    listed = await client.get("/api/personal/projects")
    assert [item["id"] for item in listed.json()] == [project_id]
    assert (await client.get(f"/api/personal/projects/{project_id}")).status_code == 200

    for target in ("active", "submitted", "won"):
        response = await client.patch(
            f"/api/personal/projects/{project_id}", json={"status": target}
        )
        assert response.status_code == 200, response.text
        assert response.json()["status"] == target

    invalid = await client.patch(f"/api/personal/projects/{project_id}", json={"status": "active"})
    assert invalid.status_code == 409
    assert "Cannot transition" in invalid.json()["detail"]

    assert (await client.delete(f"/api/personal/projects/{project_id}")).status_code == 204
    assert (await client.get(f"/api/personal/projects/{project_id}")).status_code == 404


async def test_draft_project_proposal_is_registered_with_approval(client):
    tools = (await client.get("/api/tools")).json()
    tool = next(item for item in tools if item["name"] == "draft_project_proposal")
    assert tool["requires_approval"] is True
    assert tool["enabled"] is True


async def test_daily_reminder_includes_only_next_three_days(db):
    today = date(2026, 8, 27)
    projects = [
        PersonalProject(title="Due today", status="active", due_date=today),
        PersonalProject(
            title="Due in three", status="submitted", due_date=today + timedelta(days=3)
        ),
        PersonalProject(title="Out of range", status="active", due_date=today + timedelta(days=4)),
        PersonalProject(title="Overdue", status="active", due_date=today - timedelta(days=1)),
        PersonalProject(
            title="Already complete",
            status="completed",
            due_date=today + timedelta(days=1),
        ),
        PersonalProject(title="No due date", status="active", due_date=None),
    ]
    db.add_all(projects)
    db.commit()
    reminders = daily_personal_reminder(db, today=today, within_days=3)
    assert [(item["project"].title, item["days_until_due"]) for item in reminders] == [
        ("Due today", 0),
        ("Due in three", 3),
    ]


async def test_reminder_endpoint_and_project_validation_edges(client):
    await client.post(
        "/api/personal/projects",
        json={"title": "Near", "status": "active", "due_date": "2026-08-29"},
    )
    await client.post(
        "/api/personal/projects",
        json={"title": "Far", "status": "active", "due_date": "2026-09-10"},
    )
    response = await client.get(
        "/api/personal/reminders", params={"today": "2026-08-27", "within_days": 3}
    )
    assert response.status_code == 200
    assert [item["project"]["title"] for item in response.json()] == ["Near"]

    assert (await client.post("/api/personal/projects", json={"title": "   "})).status_code == 422
    assert (
        await client.post("/api/personal/projects", json={"title": "Bad budget", "budget": -1})
    ).status_code == 422
    assert (await client.get("/api/personal/projects/99999")).status_code == 404
    assert (await client.delete("/api/personal/projects/99999")).status_code == 404
    assert (
        await client.get("/api/personal/reminders", params={"within_days": 500})
    ).status_code == 422


async def test_budget_database_constraint(db):
    db.add(PersonalProject(title="Invalid direct model", budget=Decimal("-0.01")))
    with pytest.raises(IntegrityError):
        db.commit()
    db.rollback()
