from __future__ import annotations

from unittest.mock import AsyncMock

import pytest
from sqlalchemy import select

from backend.app.models import AppSetting
from backend.app.services.secrets import (
    GEMINI_SECRET_KEY,
    delete_secret,
    get_secret,
    resolve_gemini_api_key,
    set_secret,
)

pytestmark = pytest.mark.asyncio


async def test_secret_store_encrypts_key_at_rest(db, monkeypatch, tmp_path):
    master_key_path = tmp_path / "master.key"
    monkeypatch.setenv("AGENT_MASTER_KEY_FILE", str(master_key_path))
    raw_key = "dashboard-secret-gemini-key-123456"

    record = set_secret(db, GEMINI_SECRET_KEY, raw_key, hint="••••3456")

    assert raw_key not in record.encrypted_value
    assert get_secret(db, GEMINI_SECRET_KEY) == raw_key
    monkeypatch.setenv("GEMINI_API_KEY", "older-environment-key")
    assert resolve_gemini_api_key(db) == raw_key
    assert master_key_path.exists()
    assert master_key_path.stat().st_mode & 0o777 == 0o600
    assert delete_secret(db, GEMINI_SECRET_KEY) is True
    assert get_secret(db, GEMINI_SECRET_KEY) is None


async def test_dashboard_can_validate_save_test_and_remove_gemini_key(
    client, db, monkeypatch, tmp_path
):
    monkeypatch.setenv("AGENT_MASTER_KEY_FILE", str(tmp_path / "master.key"))
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    monkeypatch.delenv("GOOGLE_API_KEY", raising=False)
    validator = AsyncMock(return_value="models/gemini-2.5-flash")
    monkeypatch.setattr("backend.app.routes.settings.validate_gemini_api_key", validator)
    raw_key = "valid-dashboard-gemini-auth-key-9876"

    saved = await client.put("/api/settings/gemini", json={"api_key": raw_key})

    assert saved.status_code == 200
    assert saved.json() == {
        "configured": True,
        "source": "dashboard",
        "hint": "••••9876",
        "validated": True,
        "model": "gemini-2.5-flash",
    }
    assert raw_key not in saved.text
    record = db.scalar(select(AppSetting).where(AppSetting.setting_key == GEMINI_SECRET_KEY))
    assert record is not None
    assert raw_key not in record.encrypted_value

    current = await client.get("/api/settings/gemini")
    assert current.status_code == 200
    assert current.json()["configured"] is True
    assert current.json()["validated"] is False

    system = await client.get("/api/system/status")
    assert system.status_code == 200
    assert system.json()["gemini_configured"] is True
    assert system.json()["gemini_key_source"] == "dashboard"
    assert raw_key not in system.text

    tested = await client.post("/api/settings/gemini/test")
    assert tested.status_code == 200
    assert tested.json()["validated"] is True
    assert validator.await_count == 2

    removed = await client.delete("/api/settings/gemini")
    assert removed.status_code == 200
    assert removed.json()["configured"] is False
    assert removed.json()["source"] == "none"


async def test_rejected_gemini_key_is_not_saved(client, db, monkeypatch, tmp_path):
    monkeypatch.setenv("AGENT_MASTER_KEY_FILE", str(tmp_path / "master.key"))
    monkeypatch.setattr(
        "backend.app.routes.settings.validate_gemini_api_key",
        AsyncMock(side_effect=RuntimeError("provider rejected secret-value")),
    )

    response = await client.put(
        "/api/settings/gemini",
        json={"api_key": "invalid-dashboard-key-123456"},
    )

    assert response.status_code == 400
    assert "secret-value" not in response.text
    assert db.scalar(select(AppSetting)) is None


async def test_short_or_missing_key_is_validation_error(client):
    assert (await client.put("/api/settings/gemini", json={})).status_code == 422
    short = await client.put("/api/settings/gemini", json={"api_key": "short"})
    assert short.status_code == 422
    assert "short" not in short.text
