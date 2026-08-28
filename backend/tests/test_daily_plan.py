"""Daily delivery plan, notifications, inline drafts, and graceful degradation."""

from __future__ import annotations

from datetime import datetime, timedelta

import pytest
from sqlalchemy import select

from backend.app.agent.ai_client import DEFAULT_GEMINI_MODEL, AIProviderError
from backend.app.assistant.service import run_chat_turn
from backend.app.models import (
    AgentConversation,
    AppNotification,
    Task,
)
from backend.app.modules.salon.models import Salon
from backend.app.scheduler import agent_timezone
from backend.app.services.daily import (
    assign_daily_deadlines,
    process_daily_brief,
    save_daily_report,
    tasks_due_on,
)

pytestmark = pytest.mark.asyncio

TZ = agent_timezone()


def _local_now(hour: int, minute: int = 0) -> datetime:
    day = datetime.now(TZ).date()
    return datetime.combine(day, datetime.min.time(), tzinfo=TZ).replace(hour=hour, minute=minute)


async def _task(db, title: str, status: str = "pending", due_at=None) -> Task:
    task = Task(title=title, status=status, due_at=due_at)
    db.add(task)
    db.commit()
    db.refresh(task)
    return task


# ---------------------------------------------------------------------------
# 1. staggered deadline assignment
# ---------------------------------------------------------------------------


async def test_assign_daily_deadlines_starts_tomorrow_one_per_day(db):
    await _task(db, "تسک یک")
    await _task(db, "تسک دو")
    await _task(db, "تسک سه")
    done = await _task(db, "تسک تمام‌شده", status="done")

    assigned = assign_daily_deadlines(db)

    assert [item["title"] for item in assigned] == ["تسک یک", "تسک دو", "تسک سه"]
    tomorrow = datetime.now(TZ).date() + timedelta(days=1)
    assert [item["due_date"] for item in assigned] == [
        (tomorrow + timedelta(days=index)).isoformat() for index in range(3)
    ]
    tasks = list(db.scalars(select(Task).order_by(Task.id)))
    assert all(task.due_at is not None for task in tasks if task.status == "pending")
    assert done.due_at is None  # finished tasks are left alone

    # Re-running is idempotent: everything already has a deadline.
    assert assign_daily_deadlines(db) == []


async def test_tasks_due_on_matches_only_that_local_day(db):
    today = datetime.now(TZ).date()
    from backend.app.services.daily import _local_due_datetime

    await _task(db, "امروز", due_at=_local_due_datetime(today))
    await _task(db, "فردا", due_at=_local_due_datetime(today + timedelta(days=1)))
    titles = [task.title for task in tasks_due_on(db, today)]
    assert titles == ["امروز"]


# ---------------------------------------------------------------------------
# 2. morning / evening brief lifecycle
# ---------------------------------------------------------------------------


async def test_morning_brief_creates_deduplicated_notification(db):
    from backend.app.services.daily import _local_due_datetime

    await _task(db, "تماس با سالن آرام", due_at=_local_due_datetime(datetime.now(TZ).date()))

    created = process_daily_brief(db, now=_local_now(8, 30))
    assert len(created) == 1
    assert created[0].kind == "morning_reminder"
    assert created[0].body["tasks"][0]["title"] == "تماس با سالن آرام"

    # Same day again: no duplicates, even after many poller ticks.
    assert process_daily_brief(db, now=_local_now(9, 0)) == []
    count = len(list(db.scalars(select(AppNotification))))
    assert count == 1


async def test_evening_brief_asks_for_report_until_one_is_saved(db):
    created = process_daily_brief(db, now=_local_now(21, 30))
    assert [item.kind for item in created] == ["evening_report"]
    assert "گزارش" in created[0].body["text"]

    # After the user submits the report, no new evening prompt appears.
    save_daily_report(db, "امروز دو تسک تمام شد.", report_date=datetime.now(TZ).date())
    assert process_daily_brief(db, now=_local_now(22, 0)) == []


async def test_brief_respects_disabled_setting_and_times(db):
    from backend.app.services.daily import update_daily_brief_settings

    update_daily_brief_settings(db, enabled=False)
    assert process_daily_brief(db, now=_local_now(23, 59)) == []

    update_daily_brief_settings(db, enabled=True, morning_time="10:00", evening_time="22:00")
    assert process_daily_brief(db, now=_local_now(9, 59)) == []


# ---------------------------------------------------------------------------
# 3. daily API + notifications API
# ---------------------------------------------------------------------------


async def test_daily_endpoints_roundtrip(client, db):
    plan = await client.get("/api/daily/plan")
    assert plan.status_code == 200
    assert plan.json()["settings"]["enabled"] is True
    assert plan.json()["settings"]["morning_time"] == "08:00"

    settings = await client.put(
        "/api/daily/settings", json={"enabled": True, "evening_time": "21:30"}
    )
    assert settings.status_code == 200
    assert settings.json()["evening_time"] == "21:30"

    bad = await client.put("/api/daily/settings", json={"morning_time": "25:99"})
    assert bad.status_code == 422

    await _task(db, "برنامه روزانه یک")
    await _task(db, "برنامه روزانه دو")
    assigned = await client.post("/api/daily/deadlines/assign")
    assert assigned.status_code == 200
    assert assigned.json()["count"] == 2

    report = await client.post("/api/daily/report", json={"content": "گزارش تست شب"})
    assert report.status_code == 200
    assert report.json()["content"] == "گزارش تست شب"
    reports = await client.get("/api/daily/reports")
    assert reports.status_code == 200
    latest = reports.json()[0]
    assert latest["content"] == "گزارش تست شب"
    assert latest["is_today"] is True

    empty = await client.post("/api/daily/report", json={"content": "   "})
    assert empty.status_code == 422


async def test_notifications_listing_and_read_all(client, db):
    db.add(
        AppNotification(
            kind="morning_reminder",
            title="یادآوری صبح",
            body={"tasks": []},
            dedupe_key="morning:test",
        )
    )
    db.commit()

    listed = await client.get("/api/notifications")
    assert listed.status_code == 200
    payload = listed.json()
    assert payload["unread"] == 1
    assert payload["notifications"][0]["title"] == "یادآوری صبح"

    read_all = await client.post("/api/notifications/read-all")
    assert read_all.status_code == 200
    assert read_all.json()["read"] == 1
    assert (await client.get("/api/notifications")).json()["unread"] == 0

    missing = await client.post("/api/notifications/9999/read")
    assert missing.status_code == 404


# ---------------------------------------------------------------------------
# 4. inline draft preview endpoint
# ---------------------------------------------------------------------------


async def test_outreach_script_preview_returns_text_without_task(client, db):
    db.add(Salon(name="سالن آزادی", phone="09120000111", city="تهران"))
    db.commit()
    salon = db.scalar(select(Salon))

    response = await client.post(
        "/api/tools/generate_outreach_script/preview",
        json={"arguments": {"salon_id": salon.id, "offer": "رشد رزرو"}},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["tool"] == "generate_outreach_script"
    assert "سالن آزادی" in body["result"]["script"]
    # No audit noise: a preview must not create tasks or steps.
    assert list(db.scalars(select(Task))) == []


async def test_preview_rejects_side_effecting_tools(client, db):
    response = await client.post(
        "/api/tools/send_telegram_message/preview", json={"arguments": {"content": "سلام"}}
    )
    assert response.status_code == 403


async def test_proposal_preview_for_personal_project(client, db):
    from backend.app.modules.personal.models import PersonalProject

    db.add(PersonalProject(title="سایت رستوران", client_name="آقای رضایی"))
    db.commit()
    project = db.scalar(select(PersonalProject))

    response = await client.post(
        "/api/tools/draft_project_proposal/preview",
        json={"arguments": {"project_id": project.id}},
    )
    assert response.status_code == 200
    assert "سایت رستوران" in response.json()["result"]["proposal"]


# ---------------------------------------------------------------------------
# 5. provider failure after successful actions is not a user-facing error
# ---------------------------------------------------------------------------


class _FailAfterActionClient:
    """Round 1: execute a tool. Round 2: provider dies. The work is still real."""

    def __init__(self):
        from backend.tests.test_agentic_assistant import FakeChatClient, FakeResult, _fc

        self._inner = FakeChatClient(
            [
                FakeResult(
                    DEFAULT_GEMINI_MODEL,
                    steps=[_fc("create_task", {"title": "تسک انجام‌شده"})],
                )
            ]
        )
        self.model = DEFAULT_GEMINI_MODEL
        self.calls = 0

    async def chat(self, **kwargs):
        self.calls += 1
        if self.calls == 1:
            return await self._inner.chat(**kwargs)
        raise AIProviderError("Gemini call failed on every configured API key")


async def test_provider_failure_after_actions_returns_success(db):
    conversation = AgentConversation(title="تست", status="active")
    db.add(conversation)
    db.commit()

    response = await run_chat_turn(
        db,
        client=_FailAfterActionClient(),
        message="یک تسک بساز",
        conversation_id=conversation.id,
    )

    actions = response["message"]["actions"]
    assert len(actions) == 1
    assert actions[0]["name"] == "create_task"
    assert "انجام و ثبت شدند" in response["message"]["content"]
    assert db.scalar(select(Task).where(Task.title == "تسک انجام‌شده")) is not None
