from __future__ import annotations

import pytest

pytestmark = pytest.mark.asyncio


async def test_system_status_reports_capabilities_without_secrets(client, monkeypatch):
    monkeypatch.setenv("GEMINI_API_KEY", "test-secret-that-must-not-leak")
    monkeypatch.setenv("EMBEDDING_BACKEND", "auto")
    monkeypatch.setenv("AGENT_TIMEZONE", "Asia/Tehran")

    response = await client.get("/api/system/status")

    assert response.status_code == 200
    body = response.json()
    assert body["api_ready"] is True
    assert body["gemini_configured"] is True
    assert body["embedding_backend"] == "gemini"
    assert body["reasoning_model"] == "gemini-3.7-flash"
    assert body["default_model"] == "gemini-3.7-flash"
    assert body["telegram_configured"] is False
    assert body["timezone"] == "Asia/Tehran"
    assert "test-secret-that-must-not-leak" not in response.text


async def test_system_status_reports_local_fallback_without_key(client, monkeypatch):
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    monkeypatch.delenv("GOOGLE_API_KEY", raising=False)
    monkeypatch.setenv("EMBEDDING_BACKEND", "auto")

    response = await client.get("/api/system/status")

    assert response.status_code == 200
    assert response.json()["gemini_configured"] is False
    assert response.json()["embedding_backend"] == "local"
