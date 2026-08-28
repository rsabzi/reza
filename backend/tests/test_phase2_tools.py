from __future__ import annotations

import pytest
from sqlalchemy.exc import IntegrityError

from backend.app.models import Tool
from backend.app.tools.registry import ToolContext, register_tool

pytestmark = pytest.mark.asyncio


async def create_task(client, title="Tool task") -> int:
    response = await client.post("/api/tasks", json={"title": title})
    assert response.status_code == 201
    return response.json()["id"]


async def test_registered_tool_appears_in_tools_endpoint(client):
    @register_tool("phase2_visible", "Visible registration", requires_approval=False)
    def visible(_context: ToolContext):
        return "visible"

    response = await client.get("/api/tools")
    assert response.status_code == 200
    item = next(tool for tool in response.json() if tool["name"] == "phase2_visible")
    assert item["description"] == "Visible registration"
    assert item["requires_approval"] is False


async def test_approval_tool_creates_paused_step_without_side_effect(client):
    side_effects: list[str] = []

    @register_tool("phase2_guarded", "Guarded", requires_approval=True)
    def guarded(_context: ToolContext, value: str):
        side_effects.append(value)
        return {"accepted": value}

    task_id = await create_task(client)
    response = await client.post(
        "/api/tools/phase2_guarded/invoke",
        json={"task_id": task_id, "arguments": {"value": "must-not-run"}},
    )
    assert response.status_code == 201
    assert response.json()["status"] == "needs_approval"
    assert response.json()["requires_approval"] is True
    assert response.json()["result"] is None
    assert side_effects == []


async def test_unrestricted_tool_executes_and_finishes_step(client):
    side_effects: list[int] = []

    @register_tool("phase2_immediate", "Immediate", requires_approval=False)
    async def immediate(_context: ToolContext, number: int):
        side_effects.append(number)
        return {"doubled": number * 2}

    task_id = await create_task(client)
    response = await client.post(
        "/api/tools/phase2_immediate/invoke",
        json={"task_id": task_id, "arguments": {"number": 4}},
    )
    assert response.status_code == 201
    assert response.json()["status"] == "done"
    assert response.json()["result"] == {"doubled": 8}
    assert side_effects == [4]


async def test_toggling_approval_changes_next_invocation(client):
    calls: list[str] = []

    @register_tool("phase2_toggle", "Toggle", requires_approval=True)
    def toggle(_context: ToolContext, marker: str):
        calls.append(marker)
        return marker

    first_task = await create_task(client, "First")
    first = await client.post(
        "/api/tools/phase2_toggle/invoke",
        json={"task_id": first_task, "arguments": {"marker": "first"}},
    )
    assert first.json()["status"] == "needs_approval"
    assert calls == []

    changed = await client.patch("/api/tools/phase2_toggle", json={"requires_approval": False})
    assert changed.status_code == 200
    assert changed.json()["requires_approval"] is False

    second_task = await create_task(client, "Second")
    second = await client.post(
        "/api/tools/phase2_toggle/invoke",
        json={"task_id": second_task, "arguments": {"marker": "second"}},
    )
    assert second.json()["status"] == "done"
    assert calls == ["second"]


async def test_tool_endpoint_failures_are_clear(client):
    task_id = await create_task(client)
    unknown = await client.post(
        "/api/tools/not_registered/invoke", json={"task_id": task_id, "arguments": {}}
    )
    assert unknown.status_code == 404
    assert "not registered" in unknown.json()["detail"]

    @register_tool("phase2_disabled", "Disabled", requires_approval=False)
    def disabled(_context: ToolContext):
        raise AssertionError("must not execute")

    assert (await client.get("/api/tools")).status_code == 200
    assert (
        await client.patch("/api/tools/phase2_disabled", json={"enabled": False})
    ).status_code == 200
    denied = await client.post(
        "/api/tools/phase2_disabled/invoke", json={"task_id": task_id, "arguments": {}}
    )
    assert denied.status_code == 403

    assert (await client.patch("/api/tools/phase2_disabled", json={})).status_code == 422
    assert (
        await client.post(
            "/api/tools/echo/invoke",
            json={"task_id": 999999, "arguments": {"value": "x"}},
        )
    ).status_code == 404

    invalid_arguments = await client.post(
        "/api/tools/echo/invoke", json={"task_id": task_id, "arguments": {}}
    )
    assert invalid_arguments.status_code == 422
    assert "Invalid arguments" in invalid_arguments.json()["detail"]


async def test_tool_name_database_constraint(db):
    db.add_all(
        [
            Tool(name="duplicate", description="one"),
            Tool(name="duplicate", description="two"),
        ]
    )
    with pytest.raises(IntegrityError):
        db.commit()
    db.rollback()
