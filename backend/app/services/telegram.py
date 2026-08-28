"""Telegram Bot API adapter with strict secret handling.

The Bot token is only ever read from the encrypted secret store; it never appears
in logs, database rows, or responses. Provider errors are redacted before they are
persisted or returned.
"""

from __future__ import annotations

import asyncio
import re
from typing import Any

import httpx
from sqlalchemy.orm import Session

from ..services.secrets import resolve_telegram_bot_token

TELEGRAM_API_BASE = "https://api.telegram.org"
TOKEN_PATTERN = re.compile(r"\d{6,12}:[A-Za-z0-9_-]{30,}")

BOT_TOKEN_MIN_LENGTH = 20
BOT_TOKEN_MAX_LENGTH = 300


class TelegramError(RuntimeError):
    """Safe, redacted Telegram provider error."""


class TelegramNetworkError(TelegramError):
    """Telegram endpoints are unreachable from this server (network/TLS/timeout)."""


def redact_text(value: str, secrets: tuple[str, ...] = ()) -> str:
    """Remove bot tokens / API keys from an error or response payload text."""

    result = TOKEN_PATTERN.sub("••••", value)
    for secret in secrets:
        if secret and len(secret) >= 8:
            result = result.replace(secret, "••••")
    return result


def _redacted_error(exc: Exception, secrets: tuple[str, ...]) -> TelegramError:
    message = str(exc) or exc.__class__.__name__
    return TelegramError(redact_text(message, secrets))


def validate_bot_token(token: str) -> str:
    normalized = token.strip()
    if not (BOT_TOKEN_MIN_LENGTH <= len(normalized) <= BOT_TOKEN_MAX_LENGTH):
        raise ValueError("Telegram bot token length is invalid")
    if not TOKEN_PATTERN.fullmatch(normalized) and ":" not in normalized:
        raise ValueError("Telegram bot token format is invalid")
    return normalized


async def telegram_get_me(db: Session, *, timeout: float = 10.0) -> dict[str, Any]:
    """Call getMe with the stored token; returns the raw (non-secret) provider payload."""

    token = resolve_telegram_bot_token(db)
    if not token:
        raise TelegramError("Telegram bot token is not configured")
    return await telegram_get_me_with_token(token, timeout=timeout)


async def telegram_get_me_with_token(token: str, *, timeout: float = 10.0) -> dict[str, Any]:
    """Call getMe with an explicit candidate token (used before it is stored)."""

    if not token:
        raise TelegramError("Telegram bot token is not configured")
    url = f"{TELEGRAM_API_BASE}/bot{token}/getMe"
    try:
        async with httpx.AsyncClient(timeout=timeout) as client:
            response = await asyncio.wait_for(client.post(url), timeout=timeout + 2.0)
        payload = response.json()
    except ValueError as exc:
        raise _redacted_error(exc, (token,)) from exc
    except (httpx.HTTPError, asyncio.TimeoutError) as exc:
        raise TelegramNetworkError(
            redact_text(str(exc) or exc.__class__.__name__, (token,))
        ) from exc
    if not payload.get("ok"):
        description = redact_text(str(payload.get("description") or payload), (token,))
        raise TelegramError(f"Telegram rejected the bot token: {description}")
    return payload


async def telegram_send_message(
    db: Session,
    *,
    chat_id: str,
    text: str,
    timeout: float = 15.0,
) -> tuple[str, dict[str, Any]]:
    """Send a message and return (provider_message_id, safe receipt)."""

    token = resolve_telegram_bot_token(db)
    if not token:
        raise TelegramError("Telegram bot token is not configured")
    if not chat_id:
        raise TelegramError("A Telegram contact chat_id is required")
    if not text.strip():
        raise TelegramError("Message content must not be blank")
    url = f"{TELEGRAM_API_BASE}/bot{token}/sendMessage"
    try:
        async with httpx.AsyncClient(timeout=timeout) as client:
            response = await asyncio.wait_for(
                client.post(url, json={"chat_id": chat_id, "text": text}),
                timeout=timeout + 2.0,
            )
        payload = response.json()
    except ValueError as exc:
        raise _redacted_error(exc, (token,)) from exc
    except (httpx.HTTPError, asyncio.TimeoutError) as exc:
        raise TelegramNetworkError(
            redact_text(str(exc) or exc.__class__.__name__, (token,))
        ) from exc
    if not payload.get("ok"):
        description = redact_text(str(payload.get("description") or payload), (token,))
        raise TelegramError(f"Telegram sendMessage failed: {description}")
    result = payload.get("result") or {}
    message_id = str(result.get("message_id") or "")
    if not message_id:
        raise TelegramError("Telegram did not return a message_id; the message was not sent")
    safe_receipt = {
        "ok": True,
        "message_id": message_id,
        "chat": result.get("chat") or {},
        "date": result.get("date"),
    }
    return message_id, safe_receipt
