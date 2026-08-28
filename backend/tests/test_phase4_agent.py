from __future__ import annotations

import json

import pytest
from sqlalchemy import select

from backend.app.agent.ai_client import get_ai_client
from backend.app.agent.executor import execute_task
from backend.app.agent.planner import PlanningError, decompose_task, parse_plan_response
from backend.app.main import app
from backend.app.models import AILog, Step, Task
from backend.app.tools.registry import ToolContext, register_tool

pytestmark = pytest.mark.asyncio


class FakeAI:
    model = "fake-gemini"

    def __init__(self, responses):
        self.responses = list(responses)
        self.prompts: list[str] = []
        self.attempt = 0

    async def generate(self, prompt: str, operation: str = "decompose_task", log_attempt=None):
        self.prompts.append(prompt)
        self.attempt += 1
        response = self.responses.pop(0)
        if isinstance(response, Exception):
            if log_attempt is not None:
                log_attempt(
                    operation=operation,
                    model=self.model,
                    attempt=self.attempt,
                    response=None,
                    error=response,
                )
            raise response
        fake_result = type(
            "FakeInteractionResult",
            (),
            {"model": self.model, "output_text": response, "steps": [], "interaction_id": "fake-1"},
        )()
        if log_attempt is not None:
            log_attempt(
                operation=operation,
                model=self.model,
                attempt=self.attempt,
                response=fake_result,
                error=None,
            )
        return response


async def test_decompose_task_with_mocked_ai_creates_expected_steps(db):
    task = Task(title="Launch campaign", description="Use saved strategy")
    db.add(task)
    db.commit()
    fake = FakeAI(
        [
            json.dumps(
                {
                    "steps": [
                        {
                            "title": "Research leads",
                            "tool_name": "echo",
                            "arguments": {"value": "leads"},
                        },
                        {"title": "Review result", "tool_name": None, "arguments": {}},
                    ]
                }
            )
        ]
    )
    steps = await decompose_task(db, task, fake)
    assert [(step.position, step.title, step.tool_name) for step in steps] == [
        (0, "Research leads", "echo"),
        (1, "Review result", None),
    ]
    assert task.status == "planned"
    logs = list(db.scalars(select(AILog).where(AILog.task_id == task.id)))
    assert len(logs) == 1
    assert logs[0].model == "fake-gemini"
    assert logs[0].response is not None


async def test_executor_stops_at_approval_and_leaves_later_steps_pending(db):
    effects: list[str] = []

    @register_tool("phase4_first", "First", requires_approval=False)
    def first(_context: ToolContext):
        effects.append("first")
        return "first done"

    @register_tool("phase4_guarded", "Guarded", requires_approval=True)
    def guarded(_context: ToolContext):
        effects.append("guarded")
        return "guarded done"

    @register_tool("phase4_later", "Later", requires_approval=False)
    def later(_context: ToolContext):
        effects.append("later")
        return "later done"

    task = Task(title="Sequence", status="planned")
    db.add(task)
    db.flush()
    db.add_all(
        [
            Step(task_id=task.id, title="First", position=0, tool_name="phase4_first"),
            Step(task_id=task.id, title="Guarded", position=1, tool_name="phase4_guarded"),
            Step(task_id=task.id, title="Later", position=2, tool_name="phase4_later"),
        ]
    )
    db.commit()

    await execute_task(db, task.id)
    db.expire_all()
    steps = list(db.scalars(select(Step).where(Step.task_id == task.id).order_by(Step.position)))
    assert [step.status for step in steps] == ["done", "needs_approval", "pending"]
    assert effects == ["first"]


async def test_approve_endpoint_resumes_current_and_remaining_steps(client):
    effects: list[str] = []

    @register_tool("phase4_e2e_guarded", "Guarded", requires_approval=True)
    def guarded(_context: ToolContext, marker: str):
        effects.append(marker)
        return {"marker": marker}

    @register_tool("phase4_e2e_after", "After", requires_approval=False)
    def after(_context: ToolContext):
        effects.append("after")
        return "done"

    task = (await client.post("/api/tasks", json={"title": "Approve E2E"})).json()
    guarded_step = (
        await client.post(
            "/api/steps",
            json={
                "task_id": task["id"],
                "title": "Need approval",
                "position": 0,
                "tool_name": "phase4_e2e_guarded",
                "arguments": {"marker": "approved"},
            },
        )
    ).json()
    await client.post(
        "/api/steps",
        json={
            "task_id": task["id"],
            "title": "After",
            "position": 1,
            "tool_name": "phase4_e2e_after",
        },
    )

    paused = await client.post(f"/api/tasks/{task['id']}/execute")
    assert paused.status_code == 200
    assert [step["status"] for step in paused.json()["steps"]] == [
        "needs_approval",
        "pending",
    ]
    assert effects == []

    resumed = await client.post(f"/api/steps/{guarded_step['id']}/approve")
    assert resumed.status_code == 200, resumed.text
    assert resumed.json()["status"] == "done"
    assert [step["status"] for step in resumed.json()["steps"]] == ["done", "done"]
    assert effects == ["approved", "after"]


async def test_ai_timeout_retries_with_backoff_and_logs_every_call(db):
    task = Task(title="Retry plan")
    db.add(task)
    db.commit()
    fake = FakeAI(
        [
            TimeoutError("Gemini timed out"),
            json.dumps(
                {
                    "steps": [
                        {
                            "title": "Recovered",
                            "tool_name": "echo",
                            "arguments": {"value": 1},
                        }
                    ]
                }
            ),
        ]
    )
    delays: list[float] = []

    async def fake_sleep(delay: float):
        delays.append(delay)

    steps = await decompose_task(db, task, fake, sleep=fake_sleep)
    assert steps[0].title == "Recovered"
    assert delays == [0.25]
    logs = list(db.scalars(select(AILog).where(AILog.task_id == task.id).order_by(AILog.attempt)))
    assert len(logs) == 2
    assert logs[0].error == "Gemini timed out"
    assert logs[1].response is not None


async def test_plan_endpoint_and_failure_edges(client):
    fake = FakeAI(
        [
            json.dumps(
                {
                    "steps": [
                        {
                            "title": "API planned",
                            "tool_name": "echo",
                            "arguments": {"value": "ok"},
                        }
                    ]
                }
            )
        ]
    )
    app.dependency_overrides[get_ai_client] = lambda: fake
    task = (await client.post("/api/tasks", json={"title": "Plan over API"})).json()
    response = await client.post(f"/api/tasks/{task['id']}/plan")
    assert response.status_code == 201
    assert response.json()[0]["title"] == "API planned"
    assert (await client.get("/api/ai-logs", params={"task_id": task["id"]})).json()[0][
        "attempt"
    ] == 1

    assert (await client.post("/api/tasks/999999/plan")).status_code == 404
    assert (await client.post("/api/tasks/999999/execute")).status_code == 404
    assert (await client.post("/api/steps/999999/approve")).status_code == 404


async def test_plan_endpoint_exhausts_retries_without_crashing_request(client, db):
    fake = FakeAI(
        [
            TimeoutError("temporary Gemini timeout"),
            TimeoutError("temporary Gemini timeout"),
            TimeoutError("temporary Gemini timeout"),
        ]
    )
    app.dependency_overrides[get_ai_client] = lambda: fake
    task = (await client.post("/api/tasks", json={"title": "Endpoint retry failure"})).json()

    response = await client.post(f"/api/tasks/{task['id']}/plan")
    assert response.status_code == 502
    assert "Planning failed after 3 attempts" in response.json()["detail"]
    db.expire_all()
    logs = list(db.scalars(select(AILog).where(AILog.task_id == task["id"])))
    assert len(logs) == 3
    assert all(log.error == "temporary Gemini timeout" for log in logs)


async def test_reject_and_invalid_approval_states(client):
    @register_tool("phase4_rejectable", "Reject", requires_approval=True)
    def rejectable(_context: ToolContext):
        raise AssertionError("must not run")

    task = (await client.post("/api/tasks", json={"title": "Reject E2E"})).json()
    step = (
        await client.post(
            "/api/steps",
            json={
                "task_id": task["id"],
                "title": "Reject",
                "position": 0,
                "tool_name": "phase4_rejectable",
            },
        )
    ).json()
    await client.post(f"/api/tasks/{task['id']}/execute")
    rejected = await client.post(f"/api/steps/{step['id']}/reject")
    assert rejected.status_code == 200
    assert rejected.json()["status"] == "cancelled"
    assert rejected.json()["steps"][0]["status"] == "cancelled"
    assert (await client.post(f"/api/steps/{step['id']}/approve")).status_code == 409


async def test_plan_parser_rejects_malformed_payloads():
    with pytest.raises(PlanningError, match="invalid JSON"):
        parse_plan_response("not json")
    with pytest.raises(PlanningError, match="non-empty"):
        parse_plan_response({"steps": []})
    with pytest.raises(PlanningError, match="missing a title"):
        parse_plan_response({"steps": [{"arguments": {}}]})
