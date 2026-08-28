"""Multi-key Gemini support: storage, rotation, cooldowns and dashboard API."""

from __future__ import annotations

import pytest
from sqlalchemy import select

from backend.app.agent.ai_client import (
    SUPPORTED_MODEL_CANDIDATES,
    AIConfigurationError,
    AIProviderError,
    GeminiInteractionsClient,
    build_interactions_client,
    is_rate_limit_error,
)
from backend.app.agent.key_pool import ApiKey, KeyPool, key_hint
from backend.app.models import AppSetting
from backend.app.services.secrets import (
    GEMINI_SECRET_KEY,
    MAX_GEMINI_KEYS,
    add_gemini_key,
    delete_all_gemini_keys,
    delete_gemini_key_slot,
    gemini_keys_overview,
    list_gemini_key_slots,
    resolve_gemini_api_key,
    resolve_gemini_api_keys,
)

pytestmark = pytest.mark.asyncio


@pytest.fixture(autouse=True)
def _fresh_shared_pool():
    from backend.app.agent.key_pool import SHARED_KEY_POOL

    SHARED_KEY_POOL.reset()
    yield
    SHARED_KEY_POOL.reset()


class _FakeInteraction:
    def __init__(self, text: str) -> None:
        self.output_text = text
        self.steps = []
        self.id = "int-1"


def _err(status_code: int, message: str) -> Exception:
    try:
        from google.genai import errors

        return errors.APIError(code=status_code, message=message, raw={})
    except Exception:  # pragma: no cover - SDK always present in tests
        return RuntimeError(f"{status_code} {message}")


# ---------------------------------------------------------------------------
# key pool primitives
# ---------------------------------------------------------------------------


async def test_key_pool_orders_active_first_and_cooling_last():
    pool = KeyPool()
    a = ApiKey.of("key-aaaa1111")
    b = ApiKey.of("key-bbbb2222")

    assert pool.order_keys([a, b]) == [a, b]
    pool.mark_success(b)
    assert pool.order_keys([a, b]) == [b, a]

    pool.mark_rate_limited(b, seconds=60)
    ordered = pool.order_keys([a, b])
    assert ordered == [a, b]  # cooling key moves to the back
    assert pool.cooling_seconds(b.value) > 0
    assert pool.has_ready_alternative([a, b], b) is True
    assert pool.has_ready_alternative([a, b], a) is False

    pool.forget(b.value)
    assert pool.active is None
    assert pool.cooling_seconds(b.value) == 0.0


async def test_key_pool_keeps_all_keys_when_everything_is_cooling():
    pool = KeyPool()
    a = ApiKey.of("key-aaaa1111")
    pool.mark_quota_exhausted(a, seconds=300)
    assert pool.order_keys([a]) == [a]


async def test_key_hint_never_reveals_more_than_four_characters():
    assert key_hint("AIzaSyA-very-long-secret-value") == "••••alue"
    assert key_hint("abc") == "••abc"
    assert key_hint("") == "••••"


# ---------------------------------------------------------------------------
# client rotation
# ---------------------------------------------------------------------------


async def test_rate_limited_key_rotates_to_next_key_without_sleep():
    attempts: list[str] = []
    logged: list[dict] = []

    class RotatingClient(GeminiInteractionsClient):
        def __init__(self):
            super().__init__(
                api_keys=["key-aaaa1111", "key-bbbb2222"],
                candidates=[SUPPORTED_MODEL_CANDIDATES[0]],
                sleep=self._fail_sleep,
                key_pool=KeyPool(),
            )
            self.keys_used: list[str] = []

        async def _fail_sleep(self, _delay):
            raise AssertionError("rotation must not sleep when an alternative key exists")

        async def _create_interaction(self, model, **payload):
            key = self._current_key
            self.keys_used.append(key.value)
            attempts.append(model)
            if key.value == "key-aaaa1111":
                raise _err(429, "RESOURCE_EXHAUSTED: per-minute rate limit exceeded")
            return _FakeInteraction("ok from second key")

    client = RotatingClient()
    result = await client.chat(input="hi", tools=[], log_attempt=lambda **kw: logged.append(kw))
    assert result.output_text == "ok from second key"
    assert client.keys_used == ["key-aaaa1111", "key-bbbb2222"]
    # The failing key is cooling down and the working key became the pointer.
    assert client._pool.active == "key-bbbb2222"
    assert client._pool.cooling_seconds("key-aaaa1111") > 0


async def test_invalid_key_rotates_then_succeeds_and_is_reported_per_hint():
    class InvalidThenOk(GeminiInteractionsClient):
        def __init__(self):
            super().__init__(api_keys=["bad-key-1111", "good-key-2222"], key_pool=KeyPool())
            self.keys_used: list[str] = []

        async def _create_interaction(self, model, **payload):
            key = self._current_key
            self.keys_used.append(key.value)
            if key.value == "bad-key-1111":
                raise _err(401, "API key not valid. Please pass a valid API key.")
            return _FakeInteraction("final")

    client = InvalidThenOk()
    result = await client.generate("plan this")
    assert result == "final"
    assert client.keys_used == ["bad-key-1111", "good-key-2222"]
    assert client._pool.last_error("bad-key-1111") == "invalid_key"


async def test_active_key_is_tried_first_on_the_next_call():
    class TwoKeyClient(GeminiInteractionsClient):
        def __init__(self, **kwargs):
            super().__init__(
                api_keys=["key-aaaa1111", "key-bbbb2222"], key_pool=KeyPool(), **kwargs
            )
            self.keys_used: list[str] = []

        async def _create_interaction(self, model, **payload):
            self.keys_used.append(self._current_key.value)
            return _FakeInteraction("ok")

    client = TwoKeyClient()
    await client.generate("one")
    await client.generate("two")
    # First call starts with slot 1; later calls stick to the connected key.
    assert client.keys_used == ["key-aaaa1111", "key-aaaa1111"]
    client._pool.mark_success(ApiKey.of("key-bbbb2222"))
    await client.generate("three")
    assert client.keys_used[-1] == "key-bbbb2222"


async def test_all_keys_failing_raises_provider_error_with_hints():
    class AlwaysLimited(GeminiInteractionsClient):
        def __init__(self):
            super().__init__(
                api_keys=["key-aaaa1111", "key-bbbb2222"],
                candidates=[SUPPORTED_MODEL_CANDIDATES[0]],
                max_retries=1,
                key_pool=KeyPool(),
            )

        async def _create_interaction(self, model, **payload):
            raise _err(429, "RESOURCE_EXHAUSTED: quota exceeded")

    client = AlwaysLimited()
    with pytest.raises(AIProviderError) as exc_info:
        await client.generate("boom")
    message = str(exc_info.value)
    assert "1111" in message and "2222" in message
    assert "key-aaaa1111" not in message  # raw values never leak


async def test_single_key_rate_limit_keeps_backoff_retry_behaviour():
    delays: list[float] = []

    async def fake_sleep(delay):
        delays.append(delay)

    class LonelyClient(GeminiInteractionsClient):
        def __init__(self):
            super().__init__(
                "key-aaaa1111",
                candidates=[SUPPORTED_MODEL_CANDIDATES[0]],
                max_retries=3,
                backoff_base=0.001,
                sleep=fake_sleep,
                key_pool=KeyPool(),
            )
            self.calls = 0

        async def _create_interaction(self, model, **payload):
            self.calls += 1
            if self.calls < 3:
                raise _err(429, "too many requests")
            return _FakeInteraction("recovered")

    client = LonelyClient()
    result = await client.generate("hi")
    assert result == "recovered"
    assert len(delays) == 2
    assert client.api_key == "key-aaaa1111"  # back-compat attribute


async def test_no_keys_at_all_raises_configuration_error():
    client = GeminiInteractionsClient(None)
    with pytest.raises(AIConfigurationError):
        await client.generate("hi")


async def test_build_interactions_client_accepts_key_list():
    client = build_interactions_client(api_keys=["key-aaaa1111", "key-bbbb2222"])
    assert [key.value for key in client._keys] == ["key-aaaa1111", "key-bbbb2222"]
    assert client.api_key == "key-aaaa1111"


async def test_rate_limit_detection_covers_sdk_and_plain_errors():
    assert is_rate_limit_error(_err(429, "RESOURCE_EXHAUSTED")) is True
    assert is_rate_limit_error(RuntimeError("429 Too Many Requests")) is True
    assert is_rate_limit_error(RuntimeError("quota exceeded for this key")) is True
    assert is_rate_limit_error(RuntimeError("some unrelated failure")) is False


# ---------------------------------------------------------------------------
# secrets storage
# ---------------------------------------------------------------------------


async def test_multiple_keys_are_stored_in_slots_and_resolved_in_order(db, monkeypatch):
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    monkeypatch.delenv("GOOGLE_API_KEY", raising=False)

    slot1 = add_gemini_key(db, "first-gemini-key-0001")
    slot2 = add_gemini_key(db, "second-gemini-key-0002")
    assert (slot1, slot2) == (1, 2)
    assert list_gemini_key_slots(db) == [1, 2]
    assert resolve_gemini_api_keys(db) == ["first-gemini-key-0001", "second-gemini-key-0002"]
    assert resolve_gemini_api_key(db) == "first-gemini-key-0001"

    overview = gemini_keys_overview(db)
    assert [item["slot"] for item in overview] == [1, 2]
    assert overview[0]["hint"] == "••••0001"
    assert overview[1]["hint"] == "••••0002"
    assert "first-gemini-key-0001" not in {
        record.encrypted_value for record in db.scalars(select(AppSetting))
    }

    # Slot 1 keeps using the legacy record key for backward compatibility.
    assert (
        db.scalar(select(AppSetting).where(AppSetting.setting_key == GEMINI_SECRET_KEY)) is not None
    )

    assert delete_gemini_key_slot(db, 1) is True
    assert list_gemini_key_slots(db) == [2]
    assert resolve_gemini_api_keys(db) == ["second-gemini-key-0002"]

    assert delete_all_gemini_keys(db) == 1
    assert resolve_gemini_api_keys(db) == []


async def test_environment_key_is_appended_as_reserve(db, monkeypatch):
    add_gemini_key(db, "dashboard-key-9876")
    monkeypatch.setenv("GEMINI_API_KEY", "environment-key-4321")
    assert resolve_gemini_api_keys(db) == ["dashboard-key-9876", "environment-key-4321"]
    monkeypatch.setenv("GEMINI_API_KEY", "dashboard-key-9876")  # never duplicated
    assert resolve_gemini_api_keys(db) == ["dashboard-key-9876"]


async def test_duplicate_and_overflow_keys_are_rejected(db):
    add_gemini_key(db, "repeated-key-5555")
    with pytest.raises(ValueError, match="قبلاً"):
        add_gemini_key(db, "repeated-key-5555")
    for index in range(MAX_GEMINI_KEYS - 1):
        add_gemini_key(db, f"filler-key-{index:04d}")
    with pytest.raises(ValueError, match="حداکثر"):
        add_gemini_key(db, "one-key-too-many-9999")


# ---------------------------------------------------------------------------
# dashboard API
# ---------------------------------------------------------------------------


async def test_dashboard_manages_rotating_keys_end_to_end(client, db, monkeypatch, tmp_path):
    from unittest.mock import AsyncMock

    monkeypatch.setenv("AGENT_MASTER_KEY_FILE", str(tmp_path / "master.key"))
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    monkeypatch.delenv("GOOGLE_API_KEY", raising=False)
    validator = AsyncMock(return_value="gemini-3.7-flash")
    monkeypatch.setattr("backend.app.routes.settings.validate_gemini_api_key", validator)

    added = await client.put("/api/settings/gemini/keys", json={"api_key": "first-key-1111"})
    assert added.status_code == 200
    body = added.json()
    assert body["count"] == 1
    assert body["keys"][0]["slot"] == 1
    assert body["keys"][0]["hint"] == "••••1111"
    assert body["max"] == 10

    second = await client.put("/api/settings/gemini/keys", json={"api_key": "second-key-2222"})
    assert second.status_code == 200
    assert second.json()["count"] == 2

    # Raw key material never appears in any response.
    assert "first-key-1111" not in second.text and "second-key-2222" not in second.text

    # Duplicate keys are rejected before hitting Google.
    duplicate = await client.put("/api/settings/gemini/keys", json={"api_key": "second-key-2222"})
    assert duplicate.status_code == 409

    removed = await client.delete("/api/settings/gemini/keys/1")
    assert removed.status_code == 200
    assert [item["slot"] for item in removed.json()["keys"]] == [2]

    missing = await client.delete("/api/settings/gemini/keys/9")
    assert missing.status_code == 404

    # Legacy DELETE /gemini now clears every stored key.
    cleared = await client.delete("/api/settings/gemini")
    assert cleared.status_code == 200
    assert cleared.json()["configured"] is False
    assert resolve_gemini_api_keys(db) == []


async def test_add_key_endpoint_validates_before_storing(client, db, monkeypatch, tmp_path):
    from unittest.mock import AsyncMock

    monkeypatch.setenv("AGENT_MASTER_KEY_FILE", str(tmp_path / "master.key"))
    monkeypatch.setattr(
        "backend.app.routes.settings.validate_gemini_api_key",
        AsyncMock(side_effect=RuntimeError("provider said no")),
    )
    response = await client.put("/api/settings/gemini/keys", json={"api_key": "unlucky-key-9999"})
    assert response.status_code == 400
    assert db.scalar(select(AppSetting)) is None


async def test_key_rotation_surfaces_in_keys_status(client, db, monkeypatch, tmp_path):
    from backend.app.agent.key_pool import SHARED_KEY_POOL
    from backend.app.services.secrets import get_gemini_key_by_slot

    monkeypatch.setenv("AGENT_MASTER_KEY_FILE", str(tmp_path / "master.key"))
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    monkeypatch.delenv("GOOGLE_API_KEY", raising=False)
    add_gemini_key(db, "primary-key-1111")
    add_gemini_key(db, "backup-key-2222")

    SHARED_KEY_POOL.mark_success(ApiKey.of("backup-key-2222"))
    SHARED_KEY_POOL.mark_rate_limited(ApiKey.of("primary-key-1111"), seconds=45)

    status = await client.get("/api/settings/gemini/keys")
    assert status.status_code == 200
    payload = status.json()
    assert payload["active_hint"] == "••••2222"
    by_slot = {item["slot"]: item for item in payload["keys"]}
    assert by_slot[2]["active"] is True
    assert by_slot[1]["active"] is False
    assert by_slot[1]["cooling_seconds"] > 0
    assert "primary-key-1111" not in status.text

    SHARED_KEY_POOL.forget("primary-key-1111")
    SHARED_KEY_POOL.forget("backup-key-2222")
    assert get_gemini_key_by_slot(db, 2) == "backup-key-2222"


async def test_redaction_covers_every_stored_key(db, monkeypatch, tmp_path):
    from backend.app.assistant.dispatcher import redact_secrets
    from backend.app.services.secrets import set_secret as set_raw_secret

    monkeypatch.setenv("AGENT_MASTER_KEY_FILE", str(tmp_path / "master.key"))
    add_gemini_key(db, "first-secret-key-1111")
    add_gemini_key(db, "second-secret-key-2222")
    set_raw_secret(db, "telegram_bot_token", "123456:ABCDEFtelegramtoken")

    dirty = "error with first-secret-key-1111 and 123456:ABCDEFtelegramtoken inside"
    clean = redact_secrets(db, dirty)
    assert "first-secret-key-1111" not in clean
    assert "123456:ABCDEFtelegramtoken" not in clean
    assert clean.count("••••") >= 2
