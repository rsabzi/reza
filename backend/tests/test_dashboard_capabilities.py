from __future__ import annotations

import pytest

pytestmark = pytest.mark.asyncio


async def test_manually_completing_last_step_finishes_parent_task(client):
    task = (await client.post("/api/tasks", json={"title": "Manual workflow"})).json()
    first = (
        await client.post(
            "/api/steps",
            json={"task_id": task["id"], "title": "First", "position": 0},
        )
    ).json()
    second = (
        await client.post(
            "/api/steps",
            json={"task_id": task["id"], "title": "Second", "position": 1},
        )
    ).json()

    await client.patch(
        f"/api/steps/{first['id']}",
        json={"status": "done", "result": {"note": "first complete"}},
    )
    assert (await client.get(f"/api/tasks/{task['id']}")).json()["status"] == "pending"

    completed = await client.patch(
        f"/api/steps/{second['id']}",
        json={"status": "done", "result": {"note": "second complete"}},
    )
    assert completed.status_code == 200
    detail = (await client.get(f"/api/tasks/{task['id']}")).json()
    assert detail["status"] == "done"
    assert [step["status"] for step in detail["steps"]] == ["done", "done"]


async def test_adding_pending_step_reopens_a_completed_task(client):
    task = (
        await client.post("/api/tasks", json={"title": "Reopen workflow", "status": "done"})
    ).json()

    created = await client.post(
        "/api/steps",
        json={"task_id": task["id"], "title": "New work", "position": 0},
    )

    assert created.status_code == 201
    detail = (await client.get(f"/api/tasks/{task['id']}")).json()
    assert detail["status"] == "pending"


async def test_task_and_step_ids_are_not_reused_after_deletion(client):
    first_task = (await client.post("/api/tasks", json={"title": "First identity"})).json()
    first_step = (
        await client.post(
            "/api/steps",
            json={"task_id": first_task["id"], "title": "First step", "position": 0},
        )
    ).json()
    await client.delete(f"/api/tasks/{first_task['id']}")

    second_task = (await client.post("/api/tasks", json={"title": "Second identity"})).json()
    second_step = (
        await client.post(
            "/api/steps",
            json={"task_id": second_task["id"], "title": "Second step", "position": 0},
        )
    ).json()

    assert second_task["id"] > first_task["id"]
    assert second_step["id"] > first_step["id"]
