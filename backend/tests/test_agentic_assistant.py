"""Agentic assistant upgrade: Interactions API, tool loop, approvals, Telegram, secrets."""

from __future__ import annotations

import json
from unittest.mock import AsyncMock

import pytest
from sqlalchemy import select

from backend.app.agent.ai_client import (
    DEFAULT_GEMINI_MODEL,
    SUPPORTED_MODEL_CANDIDATES,
    GeminiInteractionsClient,
    default_model_from_env,
)
from backend.app.assistant.dispatcher import execute_action
from backend.app.assistant.service import run_chat_turn
from backend.app.main import app
from backend.app.models import (
    AgentActionRun,
    AgentConversation,
    AgentMessage,
    AILog,
    ContactEndpoint,
    MemoryEntry,
    OutboundMessage,
    Step,
    Task,
    Tool,
)
from backend.app.modules.personal.models import PersonalProject
from backend.app.modules.salon.models import Salon
from backend.app.routes.agent import get_ai_client
from backend.app.services.telegram import TelegramError

pytestmark = pytest.mark.asyncio


class FakeStep:
    def __init__(self, *, type_, name="", arguments=None, id="call-1"):
        self.type = type_
        self.name = name
        self.arguments = arguments or {}
        self.id = id

    def model_dump(self, mode="json"):
        return {
            "type": self.type,
            "name": self.name,
            "arguments": self.arguments,
            "id": self.id,
        }


class FakeResult:
    def __init__(self, model, output_text="", steps=None, interaction_id="fake-int"):
        self.model = model
        self.output_text = output_text
        self.steps = steps or []
        self.interaction_id = interaction_id

    def function_calls(self):
        return [step for step in self.steps if getattr(step, "type", None) == "function_call"]

    def serialized_steps(self):
        return [step.model_dump() for step in self.steps]


class FakeChatClient:
    """Scripted Interactions API surrogate for the orchestration layer."""

    def __init__(self, turns, model=DEFAULT_GEMINI_MODEL):
        self.turns = list(turns)
        self.model = model
        self.inputs: list[list[dict]] = []
        self.logs: list[dict] = []

    async def chat(
        self, *, input, tools, system_instruction="", operation="assistant_chat", log_attempt=None
    ):
        self.inputs.append(list(input))
        if log_attempt is not None:
            log_attempt(
                operation=operation,
                model=self.model,
                attempt=len(self.inputs),
                response=None,
                error=None,
            )
        return self.turns.pop(0)

    async def generate(self, prompt, operation="decompose_task", log_attempt=None):
        raise AssertionError("unexpected generate call")


def _fc(name, arguments, call_id="call-1"):
    return FakeStep(type_="function_call", name=name, arguments=arguments, id=call_id)


async def _conversation(db, title="گفتگوی تست"):
    conversation = AgentConversation(title=title, status="active")
    db.add(conversation)
    db.commit()
    db.refresh(conversation)
    return conversation


# ---------------------------------------------------------------------------
# 1-3: Interactions API + model fallback + backoff logging
# ---------------------------------------------------------------------------


async def test_planner_uses_interactions_api_new_model(monkeypatch):
    created = {"model": None, "store": None, "tools": None}

    class FakeAio:
        def __init__(self):
            self.interactions = type(
                "I",
                (),
                {
                    "create": AsyncMock(
                        side_effect=lambda **kw: (
                            created.update(
                                model=kw.get("model"), store=kw.get("store"), tools=kw.get("tools")
                            )
                            or _FakeInteraction("final text")
                        )
                    )
                },
            )()

        async def __aenter__(self):
            return self

        async def __aexit__(self, *a):
            return False

    class FakeClient:
        def __init__(self, **_):
            self.aio = FakeAio()

    monkeypatch.setattr("google.genai.Client", FakeClient)
    client = GeminiInteractionsClient("test-key", candidates=list(SUPPORTED_MODEL_CANDIDATES))
    result = await client.chat(input="سلام", tools=[])
    assert created["model"] == DEFAULT_GEMINI_MODEL
    assert created["store"] is False
    assert created["tools"] == []
    assert created["model"] in SUPPORTED_MODEL_CANDIDATES
    assert default_model_from_env() == DEFAULT_GEMINI_MODEL
    assert result.output_text == "final text"


class _FakeInteraction:
    def __init__(self, text):
        self.output_text = text
        self.steps = []
        self.id = "int-1"


async def test_model_404_moves_to_next_candidate_not_retry(monkeypatch):
    attempts: list[str] = []
    logged: list[dict] = []

    class FallbackClient(GeminiInteractionsClient):
        async def _create_interaction(self, model, **payload):
            attempts.append(model)
            if model == SUPPORTED_MODEL_CANDIDATES[0]:
                exc = RuntimeError("404 NOT_FOUND model is no longer available to new users")
                raise exc
            return _FakeInteraction("ok from next")

    client = FallbackClient("test-key", candidates=list(SUPPORTED_MODEL_CANDIDATES[:3]))
    result = await client.chat(
        input="hi",
        tools=[],
        log_attempt=lambda **kw: logged.append(kw),
    )
    assert attempts == [SUPPORTED_MODEL_CANDIDATES[0], SUPPORTED_MODEL_CANDIDATES[1]]
    assert result.model == SUPPORTED_MODEL_CANDIDATES[1]
    assert result.output_text == "ok from next"
    assert len(logged) == 2
    assert logged[0]["error"] is not None


async def test_transient_timeout_retries_same_model_with_backoff(monkeypatch):
    attempts: list[str] = []
    delays: list[float] = []
    logged: list[dict] = []

    async def fake_sleep(delay):
        delays.append(delay)

    class RetryClient(GeminiInteractionsClient):
        def __init__(self):
            super().__init__(
                "test-key",
                candidates=[SUPPORTED_MODEL_CANDIDATES[0]],
                max_retries=3,
                backoff_base=0.001,
                sleep=fake_sleep,
            )
            self.calls = 0

        async def _create_interaction(self, model, **payload):
            attempts.append(model)
            self.calls += 1
            if self.calls < 3:
                import httpx

                raise httpx.TimeoutException("slow")
            return _FakeInteraction("recovered")

    client = RetryClient()
    await client.chat(input="hi", tools=[], log_attempt=lambda **kw: logged.append(kw))
    assert attempts == [SUPPORTED_MODEL_CANDIDATES[0]] * 3
    assert len(delays) == 2
    assert logged[2]["response"].output_text == "recovered"
    assert [item["attempt"] for item in logged] == [1, 2, 3]


# ---------------------------------------------------------------------------
# 4-6: dispatcher real mutations + same call_id roundtrip + multi-action
# ---------------------------------------------------------------------------


async def test_function_call_create_salon_creates_real_row(db):
    conversation = await _conversation(db)
    outcome = await execute_action(
        db,
        conversation_id=conversation.id,
        message_id=None,
        provider_call_id="call-salon-1",
        action_name="create_salon",
        arguments={"name": "سالن آفتاب", "phone": "09121234567", "city": "تهران"},
    )
    assert outcome.ok is True
    assert outcome.needs_approval is False
    assert outcome.action["result"]["salon_id"] > 0
    salon = db.scalar(select(Salon).where(Salon.phone == "09121234567"))
    assert salon is not None
    assert salon.name == "سالن آفتاب"
    assert salon.city == "تهران"
    run = db.scalar(select(AgentActionRun).where(AgentActionRun.provider_call_id == "call-salon-1"))
    assert run.status == "done"
    assert run.result["salon_id"] == salon.id


async def test_function_result_uses_same_call_id(db):
    conversation = await _conversation(db)
    outcome = await execute_action(
        db,
        conversation_id=conversation.id,
        message_id=None,
        provider_call_id="call-x",
        action_name="echo",
        arguments={"value": 42},
    )
    assert outcome.function_result["type"] == "function_result"
    assert outcome.function_result["call_id"] == "call-x"
    assert outcome.function_result["name"] == "echo"
    text = outcome.function_result["result"][0]["text"]
    assert json.loads(text)["value"] == 42


async def test_multi_action_command_performs_two_real_operations(db):
    conversation = await _conversation(db)
    client = FakeChatClient(
        [
            FakeResult(
                DEFAULT_GEMINI_MODEL,
                steps=[
                    _fc("create_salon", {"name": "سالن تست", "phone": "09990000111"}, "c1"),
                    _fc(
                        "create_task",
                        {
                            "title": "پیگیری سالن تست",
                            "scheduled_time": "09:00",
                            "recurrence_rule": "daily",
                        },
                        "c2",
                    ),
                ],
            ),
            FakeResult(DEFAULT_GEMINI_MODEL, output_text="سالن و تسک ساخته شدند."),
        ]
    )
    response = await run_chat_turn(
        db,
        client=client,
        message="سالن بساز و تسک روزانه ساعت ۹ بساز",
        conversation_id=conversation.id,
    )
    assert response["needs_approval"] is False
    assert len(response["message"]["actions"]) == 2
    assert db.scalar(select(Salon).where(Salon.phone == "09990000111")) is not None
    task = db.scalar(select(Task).where(Task.title == "پیگیری سالن تست"))
    assert task is not None
    assert task.recurrence_rule == "daily"
    assert task.scheduled_time == "09:00"
    assert "سالن و تسک ساخته شدند" in response["message"]["content"]
    # The same call ids appeared in the follow-up provider input.
    second_input = client.inputs[1]
    results = [item for item in second_input if item.get("type") == "function_result"]
    assert {item["call_id"] for item in results} == {"c1", "c2"}


# ---------------------------------------------------------------------------
# 7-10: task / project / memory / policy tools
# ---------------------------------------------------------------------------


async def test_create_and_schedule_task_from_agent(db):
    conversation = await _conversation(db)
    client = FakeChatClient(
        [
            FakeResult(
                DEFAULT_GEMINI_MODEL,
                steps=[
                    _fc(
                        "create_task",
                        {
                            "title": "چک پروژه‌ها",
                            "scheduled_time": "۹ صبح",
                            "recurrence_rule": "daily",
                        },
                        "t1",
                    )
                ],
            ),
            FakeResult(
                DEFAULT_GEMINI_MODEL,
                steps=[
                    _fc(
                        "schedule_task",
                        {
                            "task_id": 1,
                            "scheduled_time": "09:00",
                            "recurrence": True,
                        },
                        "t2",
                    )
                ],
            ),
            FakeResult(DEFAULT_GEMINI_MODEL, output_text="تسک ساخته و زمان‌بندی شد."),
        ]
    )
    response = await run_chat_turn(
        db,
        client=client,
        message="تسک چک پروژه‌ها را ساعت ۹ صبح بساز",
        conversation_id=conversation.id,
    )
    task = db.scalar(select(Task).where(Task.title == "چک پروژه‌ها"))
    assert task is not None
    assert task.scheduled_time == "09:00"
    assert task.recurrence_rule == "daily"
    assert response["message"]["actions"][0]["ok"] is True


async def test_create_update_personal_project_from_agent(db):
    conversation = await _conversation(db)
    client = FakeChatClient(
        [
            FakeResult(
                DEFAULT_GEMINI_MODEL,
                steps=[
                    _fc(
                        "create_personal_project",
                        {
                            "title": "فروشگاه سپهر",
                            "client_name": "سپهر",
                            "due_date": "شنبه",
                            "next_action": "ارسال پیش‌فاکتور",
                        },
                        "p1",
                    )
                ],
            ),
            FakeResult(
                DEFAULT_GEMINI_MODEL,
                steps=[
                    _fc(
                        "update_personal_project",
                        {
                            "project_id": 1,
                            "status": "active",
                        },
                        "p2",
                    )
                ],
            ),
            FakeResult(DEFAULT_GEMINI_MODEL, output_text="پروژه ساخته و فعال شد."),
        ]
    )
    await run_chat_turn(
        db,
        client=client,
        message="پروژه فروشگاه سپهر را بساز و فعال کن",
        conversation_id=conversation.id,
    )
    project = db.scalar(select(PersonalProject).where(PersonalProject.title == "فروشگاه سپهر"))
    assert project is not None
    assert project.status == "active"
    assert project.due_date is not None


async def test_search_memory_from_agent(db):
    conversation = await _conversation(db)
    memory = MemoryEntry(
        content="پلی‌بوک پیگیری سالن‌ها: تماس هر ۷ روز",
        source="playbook",
        source_id="1",
        module_name="salon",
        embedding=[0.1] * 128,
        entry_metadata={},
    )
    db.add(memory)
    db.commit()
    client = FakeChatClient(
        [
            FakeResult(
                DEFAULT_GEMINI_MODEL,
                steps=[
                    _fc(
                        "search_memory",
                        {
                            "query": "کادنس پیگیری سالن",
                            "limit": 3,
                        },
                        "m1",
                    )
                ],
            ),
            FakeResult(DEFAULT_GEMINI_MODEL, output_text="کادنس ۷ روز است."),
        ]
    )
    response = await run_chat_turn(
        db, client=client, message="کادنس پیگیری سالن‌ها را بگو", conversation_id=conversation.id
    )
    assert response["message"]["actions"][0]["ok"] is True
    assert response["message"]["actions"][0]["result"]["count"] == 1


async def test_change_tool_policy_from_agent(db):
    conversation = await _conversation(db)
    client = FakeChatClient(
        [
            FakeResult(
                DEFAULT_GEMINI_MODEL,
                steps=[
                    _fc(
                        "set_tool_policy",
                        {
                            "tool_name": "echo",
                            "enabled": False,
                        },
                        "s1",
                    )
                ],
            ),
            FakeResult(DEFAULT_GEMINI_MODEL, output_text="ابزار echo غیرفعال شد."),
        ]
    )
    await run_chat_turn(
        db, client=client, message="ابزار echo را غیرفعال کن", conversation_id=conversation.id
    )
    record = db.scalar(select(Tool).where(Tool.name == "echo"))
    assert record is not None
    assert record.enabled is False


# ---------------------------------------------------------------------------
# 11-15: idempotency, approval, no-key 409, CRUD
# ---------------------------------------------------------------------------


async def test_advice_only_request_creates_no_business_mutation(db):
    conversation = await _conversation(db)
    client = FakeChatClient(
        [FakeResult(DEFAULT_GEMINI_MODEL, output_text="امروز اول سالن آفتاب را پیگیری کن.")]
    )
    await run_chat_turn(
        db, client=client, message="امروز چه کاری پیشنهاد می‌دهی؟", conversation_id=conversation.id
    )
    assert db.scalar(select(Salon)) is None
    assert db.scalar(select(Task)) is None
    assert db.scalar(select(PersonalProject)) is None
    assert db.scalar(select(MemoryEntry)) is None


async def test_duplicate_call_id_not_executed_twice(db):
    conversation = await _conversation(db)
    first = await execute_action(
        db,
        conversation_id=conversation.id,
        message_id=None,
        provider_call_id="dup-1",
        action_name="create_salon",
        arguments={"name": "سالن تکراری", "phone": "09120000000"},
    )
    second = await execute_action(
        db,
        conversation_id=conversation.id,
        message_id=None,
        provider_call_id="dup-1",
        action_name="create_salon",
        arguments={"name": "سالن تکراری", "phone": "09120000000"},
    )
    assert first.ok is True
    assert second.ok is True
    assert second.action.get("idempotent") is True
    assert db.scalar(select(Salon).where(Salon.phone == "09120000000")) is not None
    assert len(db.scalars(select(Salon).where(Salon.phone == "09120000000")).all()) == 1


async def test_delete_not_run_before_approve_and_exactly_once_after(client, db):
    salon = Salon(name="سالن حذف", phone="09125550000", status="lead")
    db.add(salon)
    db.commit()
    db.refresh(salon)
    conversation = await _conversation(db)
    outcome = await execute_action(
        db,
        conversation_id=conversation.id,
        message_id=None,
        provider_call_id="del-1",
        action_name="delete_application_record",
        arguments={"resource_type": "salon", "resource_id": salon.id},
    )
    assert outcome.needs_approval is True
    assert db.get(Salon, salon.id) is not None  # not deleted before approval
    step = db.scalar(select(Step).where(Step.tool_name == "delete_application_record"))
    assert step is not None and step.status == "needs_approval"

    approved = await client.post(f"/api/steps/{step.id}/approve")
    assert approved.status_code == 200, approved.text
    db.expunge(salon)
    assert db.scalar(select(Salon).where(Salon.id == salon.id)) is None
    run = db.scalar(select(AgentActionRun).where(AgentActionRun.provider_call_id == "del-1"))
    assert run.status == "done"
    assert run.result["deleted"] is True

    second = await client.post(f"/api/steps/{step.id}/approve")
    assert second.status_code == 409
    assert db.scalar(select(Salon).where(Salon.id == salon.id)) is None


async def test_outreach_and_proposal_require_approval(db):
    salon = Salon(name="سالن پیگیری", phone="09127770000", status="lead")
    db.add(salon)
    db.commit()
    db.refresh(salon)
    project = PersonalProject(title="پروژه نمونه", status="lead")
    db.add(project)
    db.commit()
    db.refresh(project)
    conversation = await _conversation(db)

    outreach = await execute_action(
        db,
        conversation_id=conversation.id,
        message_id=None,
        provider_call_id="out-1",
        action_name="prepare_salon_outreach",
        arguments={"salon_id": salon.id},
    )
    assert outreach.needs_approval is True
    assert outreach.action["result"] is None
    proposal = await execute_action(
        db,
        conversation_id=conversation.id,
        message_id=None,
        provider_call_id="pro-1",
        action_name="prepare_project_proposal",
        arguments={"project_id": project.id},
    )
    assert proposal.needs_approval is True


async def test_chat_without_gemini_key_returns_409(client, monkeypatch):
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    monkeypatch.delenv("GOOGLE_API_KEY", raising=False)
    app.dependency_overrides[get_ai_client] = lambda: GeminiInteractionsClient(None)
    response = await client.post(
        "/api/assistant/chat", json={"message": "سلام", "conversation_id": None}
    )
    assert response.status_code == 409
    assert "Gemini" in response.json().get("detail", "")
    app.dependency_overrides.pop(get_ai_client, None)


async def test_conversation_crud_and_cascade(client, db):
    created = await client.post("/api/assistant/conversations", json={"title": "گفتگوی CRUD"})
    assert created.status_code == 201
    conversation_id = created.json()["id"]
    db.add(AgentMessage(conversation_id=conversation_id, role="user", content="سلام", actions=[]))
    db.add(
        AgentMessage(conversation_id=conversation_id, role="assistant", content="سلام!", actions=[])
    )
    db.add(
        AgentActionRun(
            conversation_id=conversation_id,
            message_id=None,
            provider_call_id="crd-1",
            action_name="echo",
            arguments={"value": 1},
            status="done",
            result={"value": 1},
        )
    )
    db.commit()
    detail = await client.get(f"/api/assistant/conversations/{conversation_id}")
    assert detail.status_code == 200
    assert len(detail.json()["messages"]) == 2
    listed = await client.get("/api/assistant/conversations")
    assert any(item["id"] == conversation_id for item in listed.json())
    archived = await client.post(f"/api/assistant/conversations/{conversation_id}/archive")
    assert archived.status_code == 200
    assert archived.json()["status"] == "archived"
    deleted = await client.delete(f"/api/assistant/conversations/{conversation_id}")
    assert deleted.status_code == 204
    assert db.get(AgentConversation, conversation_id) is None
    assert (
        db.scalar(select(AgentMessage).where(AgentMessage.conversation_id == conversation_id))
        is None
    )
    assert (
        db.scalar(select(AgentActionRun).where(AgentActionRun.provider_call_id == "crd-1")) is None
    )


# ---------------------------------------------------------------------------
# 17: secrets never leak
# ---------------------------------------------------------------------------


async def test_secrets_never_appear_in_responses_logs_or_errors(client, db, monkeypatch, tmp_path):
    monkeypatch.setenv("AGENT_MASTER_KEY_FILE", str(tmp_path / "master.key"))
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    from backend.app.agent.ai_client import DEFAULT_GEMINI_MODEL

    validator = AsyncMock(return_value=DEFAULT_GEMINI_MODEL)
    monkeypatch.setattr("backend.app.routes.settings.validate_gemini_api_key", validator)
    gemini_key = "gemini-secret-that-must-not-leak-123456"
    saved = await client.put("/api/settings/gemini", json={"api_key": gemini_key})
    assert gemini_key not in saved.text

    token = "123456789:AAAbbbCCCdddEEEfffGGGhhhIIIjjjKKK"
    mock_get_me = AsyncMock(return_value={"ok": True, "result": {"username": "agent_bot"}})
    monkeypatch.setattr("backend.app.routes.settings.telegram_get_me_with_token", mock_get_me)
    telegram_save = await client.put("/api/settings/telegram", json={"bot_token": token})
    assert telegram_save.status_code == 200, telegram_save.text
    assert token not in telegram_save.text
    current = await client.get("/api/settings/telegram")
    assert token not in current.text
    assert current.json()["hint"].endswith(token[-4:])

    conversation = await _conversation(db)
    outcome = await execute_action(
        db,
        conversation_id=conversation.id,
        message_id=None,
        provider_call_id="sec-1",
        action_name="echo",
        arguments={"value": "not-a-secret"},
    )
    assert outcome.ok is True
    log_text = json.dumps(
        [{"error": item.error, "prompt": item.prompt} for item in db.scalars(select(AILog))]
    )
    assert gemini_key not in log_text
    assert token not in log_text
    run_text = json.dumps([{"error": item.error} for item in db.scalars(select(AgentActionRun))])
    assert gemini_key not in run_text
    assert token not in run_text


# ---------------------------------------------------------------------------
# 18-22: Telegram provider flows
# ---------------------------------------------------------------------------


class FakeTelegramResponse:
    def __init__(self, payload, status_code=200):
        self._payload = payload
        self.status_code = status_code

    def json(self):
        return self._payload


async def test_telegram_get_me_success_invalid_timeout(monkeypatch):
    from backend.app.services import telegram as tg

    calls: list[str] = []

    class FakeAsyncClient:
        def __init__(self, **kwargs):
            self._kwargs = kwargs

        async def __aenter__(self):
            return self

        async def __aexit__(self, *a):
            return False

        async def post(self, url, **kwargs):
            calls.append(url)
            return self._payload

    async def timeout_post(self, url, **kwargs):
        import httpx

        raise httpx.TimeoutException("timeout")

    # success
    monkeypatch.setattr(
        tg.httpx,
        "AsyncClient",
        lambda **kw: _PayloadClient({"ok": True, "result": {"username": "agent_bot"}}),
    )
    payload = await tg.telegram_get_me_with_token("123456789:AAAbbbCCCdddEEEfffGGGhhhIIIjjjKKK")
    assert payload["ok"] is True
    assert payload["result"]["username"] == "agent_bot"

    # invalid token
    monkeypatch.setattr(
        tg.httpx,
        "AsyncClient",
        lambda **kw: _PayloadClient({"ok": False, "description": "Unauthorized"}),
    )
    with pytest.raises(TelegramError, match="Unauthorized"):
        await tg.telegram_get_me_with_token("123456789:AAAbbbCCCdddEEEfffGGGhhhIIIjjjKKK")

    # timeout
    class TimeoutClient(FakeAsyncClient):
        async def post(self, url, **kwargs):
            import httpx

            raise httpx.TimeoutException("slow")

    monkeypatch.setattr(tg.httpx, "AsyncClient", lambda **kw: TimeoutClient(payload=None))
    with pytest.raises(TelegramError):
        await tg.telegram_get_me_with_token("123456789:AAAbbbCCCdddEEEfffGGGhhhIIIjjjKKK")


class _PayloadClient:
    def __init__(self, payload, **_):
        self._payload = payload

    async def __aenter__(self):
        return self

    async def __aexit__(self, *a):
        return False

    async def post(self, url, **kwargs):
        return FakeTelegramResponse(self._payload)


async def test_telegram_send_before_approve_zero_calls(client, db, monkeypatch, tmp_path):
    monkeypatch.setenv("AGENT_MASTER_KEY_FILE", str(tmp_path / "master.key"))
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    monkeypatch.delenv("TELEGRAM_BOT_TOKEN", raising=False)
    token = "123456789:AAAbbbCCCdddEEEfffGGGhhhIIIjjjKKK"
    from backend.app.services.secrets import TELEGRAM_SECRET_KEY, set_secret

    set_secret(db, TELEGRAM_SECRET_KEY, token, hint="••••KKK")
    contact = ContactEndpoint(
        owner_type="general",
        owner_id=None,
        channel="telegram",
        address="987654321",
        label="کارفرما",
        enabled=True,
    )
    db.add(contact)
    db.commit()
    db.refresh(contact)
    sent = AsyncMock(return_value=("777", {"ok": True, "message_id": "777"}))
    monkeypatch.setattr("backend.app.assistant.tools.telegram_send_message", sent)
    conversation = await _conversation(db)
    outcome = await execute_action(
        db,
        conversation_id=conversation.id,
        message_id=None,
        provider_call_id="tg-1",
        action_name="send_telegram_message",
        arguments={"content": "پیام تست", "owner_type": "general"},
    )
    assert outcome.needs_approval is True
    sent.assert_not_called()
    message = db.scalar(select(OutboundMessage).where(OutboundMessage.idempotency_key == "tg-1"))
    assert message.status == "needs_approval"
    step = db.scalar(select(Step).where(Step.tool_name == "send_telegram_message"))
    approved = await client.post(f"/api/steps/{step.id}/approve")
    assert approved.status_code == 200, approved.text
    sent.assert_awaited_once()
    db.refresh(message)
    assert message.status == "sent"
    assert message.provider_message_id == "777"
    assert message.provider_response["message_id"] == "777"
    again = await client.post(f"/api/steps/{step.id}/approve")
    assert again.status_code == 409
    sent.assert_awaited_once()


async def test_telegram_failure_marks_failed_without_crash(client, db, monkeypatch, tmp_path):
    monkeypatch.setenv("AGENT_MASTER_KEY_FILE", str(tmp_path / "master.key"))
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    monkeypatch.delenv("TELEGRAM_BOT_TOKEN", raising=False)
    token = "123456789:AAAbbbCCCdddEEEfffGGGhhhIIIjjjKKK"
    from backend.app.services.secrets import TELEGRAM_SECRET_KEY, set_secret

    set_secret(db, TELEGRAM_SECRET_KEY, token, hint="••••KKK")
    contact = ContactEndpoint(
        owner_type="general",
        owner_id=None,
        channel="telegram",
        address="111",
        enabled=True,
    )
    db.add(contact)
    db.commit()
    db.refresh(contact)
    monkeypatch.setattr(
        "backend.app.assistant.tools.telegram_send_message",
        AsyncMock(side_effect=TelegramError("sendMessage failed: Bad Request")),
    )
    conversation = await _conversation(db)
    outcome = await execute_action(
        db,
        conversation_id=conversation.id,
        message_id=None,
        provider_call_id="tg-fail",
        action_name="send_telegram_message",
        arguments={"content": "پیام", "owner_type": "general"},
    )
    assert outcome.needs_approval is True
    step = db.scalar(select(Step).where(Step.tool_name == "send_telegram_message"))
    response = await client.post(f"/api/steps/{step.id}/approve")
    assert response.status_code == 502
    message = db.scalar(select(OutboundMessage).where(OutboundMessage.idempotency_key == "tg-fail"))
    assert message.status == "failed"
    run = db.scalar(select(AgentActionRun).where(AgentActionRun.provider_call_id == "tg-fail"))
    assert run.status == "failed"


async def test_chat_endpoint_full_tool_round(client, db, monkeypatch, tmp_path):
    """API-level chat: model function calls execute real tools and return an audit card."""

    monkeypatch.setenv("AGENT_MASTER_KEY_FILE", str(tmp_path / "master.key"))
    from backend.app.services.secrets import GEMINI_SECRET_KEY, set_secret

    set_secret(db, GEMINI_SECRET_KEY, "valid-test-gemini-key-1234567", hint="••••4567")
    fake = FakeChatClient(
        [
            FakeResult(
                DEFAULT_GEMINI_MODEL,
                steps=[
                    _fc(
                        "create_salon",
                        {"name": "سالن API", "phone": "09129998877", "city": "شیراز"},
                        "api-call-1",
                    )
                ],
            ),
            FakeResult(DEFAULT_GEMINI_MODEL, output_text="سالن API با شناسه ۱ ایجاد شد."),
        ]
    )
    app.dependency_overrides[get_ai_client] = lambda: fake
    try:
        response = await client.post(
            "/api/assistant/chat",
            json={"message": "یک سالن API در شیراز اضافه کن", "conversation_id": None},
        )
    finally:
        app.dependency_overrides.pop(get_ai_client, None)
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["model"] == DEFAULT_GEMINI_MODEL
    assert body["needs_approval"] is False
    assert body["message"]["content"] == "سالن API با شناسه ۱ ایجاد شد."
    assert body["message"]["actions"][0]["name"] == "create_salon"
    assert body["message"]["actions"][0]["ok"] is True
    salon = db.scalar(select(Salon).where(Salon.phone == "09129998877"))
    assert salon is not None
    assert salon.city == "شیراز"
    detail = await client.get(f"/api/assistant/conversations/{body['conversation_id']}")
    assert detail.status_code == 200
    runs = detail.json()["action_runs"]
    assert len(runs) == 1
    assert runs[0]["provider_call_id"] == "api-call-1"
    assert runs[0]["status"] == "done"
    assert len(detail.json()["messages"]) == 2


async def test_validation_errors_never_echo_raw_secret(client):
    """Wrong-type secret inputs must not leak the submitted value back."""

    raw = "SUPER-SECRET-TOKEN-1234567890-ABCDEF"
    telegram = await client.put("/api/settings/telegram", json={"bot_token": [raw]})
    assert telegram.status_code == 422
    assert raw not in telegram.text

    gemini = await client.put("/api/settings/gemini", json={"api_key": [raw]})
    assert gemini.status_code == 422
    assert raw not in gemini.text

    too_long = await client.put("/api/settings/telegram", json={"bot_token": "x" * 400})
    assert too_long.status_code == 422
    assert "x" * 400 not in too_long.text


async def test_widening_tool_policy_requires_approval(client, db):
    """Re-enabling a tool / removing its approval gate needs user confirmation."""

    from backend.app.services.permissions import sync_registered_tools

    sync_registered_tools(db)
    tool = db.scalar(select(Tool).where(Tool.name == "echo"))
    assert tool is not None
    tool.enabled = False
    db.commit()
    conversation = await _conversation(db)

    # Widening (enable a disabled tool) -> must pause at approval.
    outcome = await execute_action(
        db,
        conversation_id=conversation.id,
        message_id=None,
        provider_call_id="widen-1",
        action_name="set_tool_policy",
        arguments={"tool_name": "echo", "enabled": True},
    )
    assert outcome.needs_approval is True
    assert db.scalar(select(Tool).where(Tool.name == "echo")).enabled is False
    step = db.scalar(select(Step).where(Step.tool_name == "set_tool_policy"))
    approved = await client.post(f"/api/steps/{step.id}/approve")
    assert approved.status_code == 200, approved.text
    db.expunge(tool)
    assert db.scalar(select(Tool).where(Tool.name == "echo")).enabled is True

    # Restrictive change (disable) still executes directly, no approval needed.
    db.scalar(select(Tool).where(Tool.name == "echo")).enabled = True
    db.commit()
    direct = await execute_action(
        db,
        conversation_id=conversation.id,
        message_id=None,
        provider_call_id="restrict-1",
        action_name="set_tool_policy",
        arguments={"tool_name": "echo", "enabled": False},
    )
    assert direct.needs_approval is False
    assert direct.ok is True
