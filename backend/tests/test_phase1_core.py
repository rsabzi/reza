from __future__ import annotations

import pytest
from sqlalchemy import select

from backend.app.models import Step

pytestmark = pytest.mark.asyncio


async def test_task_full_crud(client):
    created = await client.post(
        "/api/tasks", json={"title": "Write proposal", "description": "For ACME"}
    )
    assert created.status_code == 201
    task_id = created.json()["id"]
    assert created.json()["status"] == "pending"

    listed = await client.get("/api/tasks")
    assert listed.status_code == 200
    assert [item["id"] for item in listed.json()] == [task_id]

    fetched = await client.get(f"/api/tasks/{task_id}")
    assert fetched.status_code == 200
    assert fetched.json()["title"] == "Write proposal"
    assert fetched.json()["steps"] == []

    updated = await client.patch(
        f"/api/tasks/{task_id}",
        json={"title": "Write polished proposal", "status": "running"},
    )
    assert updated.status_code == 200
    assert updated.json()["title"] == "Write polished proposal"
    assert updated.json()["status"] == "running"

    deleted = await client.delete(f"/api/tasks/{task_id}")
    assert deleted.status_code == 204
    assert (await client.get(f"/api/tasks/{task_id}")).status_code == 404


async def test_step_full_crud_and_parent_link(client):
    task = (await client.post("/api/tasks", json={"title": "Parent"})).json()
    created = await client.post(
        "/api/steps",
        json={"task_id": task["id"], "title": "Research", "position": 0},
    )
    assert created.status_code == 201
    step_id = created.json()["id"]
    assert created.json()["task_id"] == task["id"]

    fetched = await client.get(f"/api/steps/{step_id}")
    assert fetched.status_code == 200
    assert fetched.json()["title"] == "Research"

    updated = await client.patch(
        f"/api/steps/{step_id}", json={"title": "Deep research", "status": "running"}
    )
    assert updated.status_code == 200
    assert updated.json()["title"] == "Deep research"

    listed = await client.get("/api/steps", params={"task_id": task["id"]})
    assert len(listed.json()) == 1

    deleted = await client.delete(f"/api/steps/{step_id}")
    assert deleted.status_code == 204
    assert (await client.get(f"/api/steps/{step_id}")).status_code == 404


async def test_deleting_task_cascades_to_steps(client, db):
    task = (await client.post("/api/tasks", json={"title": "Cascading parent"})).json()
    step = (
        await client.post(
            "/api/steps", json={"task_id": task["id"], "title": "Child", "position": 0}
        )
    ).json()

    assert (await client.delete(f"/api/tasks/{task['id']}")).status_code == 204
    db.expire_all()
    assert db.scalar(select(Step).where(Step.id == step["id"])) is None


async def test_validation_and_duplicate_position_errors(client):
    missing = await client.post("/api/tasks", json={"description": "No title"})
    assert missing.status_code == 422
    assert missing.json()["detail"][0]["loc"][-1] == "title"

    blank = await client.post("/api/tasks", json={"title": "   "})
    assert blank.status_code == 422
    assert "blank" in blank.text

    task = (await client.post("/api/tasks", json={"title": "Positions"})).json()
    payload = {"task_id": task["id"], "title": "One", "position": 0}
    assert (await client.post("/api/steps", json=payload)).status_code == 201
    duplicate = await client.post("/api/steps", json={**payload, "title": "Duplicate"})
    assert duplicate.status_code == 409
    assert "position" in duplicate.json()["detail"]


async def test_missing_records_return_404(client):
    assert (await client.get("/api/tasks/99999")).status_code == 404
    assert (await client.patch("/api/tasks/99999", json={"status": "done"})).status_code == 404
    assert (await client.delete("/api/tasks/99999")).status_code == 404
    assert (await client.get("/api/steps/99999")).status_code == 404
    assert (
        await client.post("/api/steps", json={"task_id": 99999, "title": "Orphan", "position": 0})
    ).status_code == 404
