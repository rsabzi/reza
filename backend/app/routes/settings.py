"""Secure, server-side runtime settings managed from the local dashboard."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy.orm import Session

from ..agent.ai_client import (
    SUPPORTED_MODEL_CANDIDATES,
    GeminiInvalidKeyError,
    GeminiNetworkError,
    ModelUnavailableError,
    default_model_from_env,
)
from ..agent.key_pool import SHARED_KEY_POOL
from ..database import get_db
from ..services.preferences import (
    MODEL_PREFERENCE_KEY,
    REMINDER_WINDOW_KEY,
    get_preference,
    resolved_model_name,
    set_preference,
)
from ..services.secrets import (
    GEMINI_SECRET_KEY,
    MAX_GEMINI_KEYS,
    TELEGRAM_SECRET_KEY,
    SecretStoreError,
    add_gemini_key,
    delete_all_gemini_keys,
    delete_gemini_key_slot,
    delete_secret,
    environment_gemini_key,
    gemini_keys_overview,
    gemini_secret_status,
    get_gemini_key_by_slot,
    list_gemini_key_slots,
    redact_stored_secrets,
    resolve_gemini_api_keys,
    set_secret,
    telegram_secret_status,
)
from ..services.telegram import (
    TelegramError,
    TelegramNetworkError,
    telegram_get_me_with_token,
    validate_bot_token,
)

router = APIRouter(prefix="/settings", tags=["settings"])


class GeminiKeyInput(BaseModel):
    # `Any` + manual redacted validation: Pydantic errors must never echo the
    # submitted secret value back to the client.
    api_key: Any


class GeminiModelInput(BaseModel):
    model: str


class GeminiKeyStatus(BaseModel):
    slot: int
    hint: str | None
    active: bool = False
    cooling_seconds: float = 0.0
    last_error: str | None = None


class GeminiKeysStatus(BaseModel):
    keys: list[GeminiKeyStatus]
    count: int
    max: int
    active_hint: str | None = None
    environment: bool = False


class GeminiSettingStatus(BaseModel):
    configured: bool
    source: str
    hint: str | None
    validated: bool = False
    model: str
    models: list[str]


class TelegramTokenInput(BaseModel):
    # `Any` + manual redacted validation (see GeminiKeyInput).
    bot_token: Any


class TelegramSettingStatus(BaseModel):
    configured: bool
    source: str
    hint: str | None
    validated: bool = False


async def validate_gemini_api_key(api_key: str) -> str:
    """Validate a key through model discovery; returns the first supported model."""

    from ..agent.ai_client import validate_gemini_api_key as provider_validate

    model, _ = await provider_validate(api_key)
    return model


async def _validated_key_or_http_error(api_key: str) -> str:
    """Validate a key with Google or raise the matching user-facing HTTP error."""

    try:
        return await validate_gemini_api_key(api_key)
    except TimeoutError as exc:
        raise HTTPException(
            status_code=status.HTTP_504_GATEWAY_TIMEOUT,
            detail="Google Gemini did not respond in time; the key was not saved",
        ) from exc
    except GeminiInvalidKeyError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Google این کلید را رد کرد؛ کلید Gemini را بررسی کنید (the key was not saved)",
        ) from exc
    except (GeminiNetworkError, ModelUnavailableError) as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=(
                "سرور فعلی به سرویس Google دسترسی ندارد (شبکه/TLS/proxy)؛ "
                "اتصال سرور را بررسی کنید (the key was not saved)"
            ),
        ) from exc
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Google rejected the Gemini key or the service is unreachable; the key was not saved",
        ) from exc


async def discover_supported_models(api_key: str) -> list[str]:
    from ..agent.ai_client import list_available_models, supported_models_overlap

    available = await list_available_models(api_key)
    supported = supported_models_overlap(available)
    return list(supported) or list(SUPPORTED_MODEL_CANDIDATES)


def _gemini_status(db: Session, *, validated: bool = False) -> GeminiSettingStatus:
    try:
        current = gemini_secret_status(db)
    except SecretStoreError as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc
    model = resolved_model_name(db, default_model_from_env())
    return GeminiSettingStatus(
        **current,
        validated=validated,
        model=model,
        models=list(SUPPORTED_MODEL_CANDIDATES),
    )


@router.get("/gemini", response_model=GeminiSettingStatus)
def get_gemini_setting(db: Session = Depends(get_db)) -> GeminiSettingStatus:
    return _gemini_status(db)


@router.put("/gemini", response_model=GeminiSettingStatus)
async def save_gemini_setting(
    payload: GeminiKeyInput,
    db: Session = Depends(get_db),
) -> GeminiSettingStatus:
    if not isinstance(payload.api_key, str):
        raise HTTPException(status_code=422, detail="Gemini API key must be a string")
    api_key = payload.api_key.strip()
    if not 10 <= len(api_key) <= 500:
        raise HTTPException(status_code=422, detail="Gemini API key length is invalid")
    discovered = await _validated_key_or_http_error(api_key)

    try:
        set_secret(
            db,
            GEMINI_SECRET_KEY,
            api_key,
            hint=f"••••{api_key[-4:]}",
        )
        SHARED_KEY_POOL.forget(api_key)
        model_status = _gemini_status(db, validated=True).model_dump()
        model_status["model"] = discovered
        if get_preference(db, MODEL_PREFERENCE_KEY) is None:
            set_preference(db, MODEL_PREFERENCE_KEY, discovered)
            model_status["model"] = discovered
        return GeminiSettingStatus(**model_status)
    except (SecretStoreError, ValueError) as exc:
        raise HTTPException(status_code=500, detail=f"Could not store Gemini key: {exc}") from exc


def _gemini_keys_status(db: Session) -> GeminiKeysStatus:
    keys: list[GeminiKeyStatus] = []
    active_value = SHARED_KEY_POOL.active
    active_hint: str | None = None
    for item in gemini_keys_overview(db):
        value = get_gemini_key_by_slot(db, item["slot"]) or ""
        is_active = bool(value) and value == active_value
        last_error = SHARED_KEY_POOL.last_error(value) if value else None
        keys.append(
            GeminiKeyStatus(
                slot=item["slot"],
                hint=item["hint"],
                active=is_active,
                cooling_seconds=SHARED_KEY_POOL.cooling_seconds(value) if value else 0.0,
                last_error=(redact_stored_secrets(db, last_error) or None if last_error else None),
            )
        )
        if is_active and item["hint"]:
            active_hint = item["hint"]
    return GeminiKeysStatus(
        keys=keys,
        count=len(keys),
        max=MAX_GEMINI_KEYS,
        active_hint=active_hint,
        environment=bool(environment_gemini_key()),
    )


@router.get("/gemini/keys", response_model=GeminiKeysStatus)
def get_gemini_keys(db: Session = Depends(get_db)) -> GeminiKeysStatus:
    try:
        return _gemini_keys_status(db)
    except SecretStoreError as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@router.put("/gemini/keys", response_model=GeminiKeysStatus)
async def add_gemini_key_route(
    payload: GeminiKeyInput,
    db: Session = Depends(get_db),
) -> GeminiKeysStatus:
    """Add one more rotating Gemini key (validated first, stored encrypted)."""

    if not isinstance(payload.api_key, str):
        raise HTTPException(status_code=422, detail="Gemini API key must be a string")
    api_key = payload.api_key.strip()
    if not 10 <= len(api_key) <= 500:
        raise HTTPException(status_code=422, detail="Gemini API key length is invalid")
    discovered = await _validated_key_or_http_error(api_key)

    try:
        had_keys = bool(list_gemini_key_slots(db))
        add_gemini_key(db, api_key)
        SHARED_KEY_POOL.forget(api_key)
        if not had_keys and get_preference(db, MODEL_PREFERENCE_KEY) is None:
            set_preference(db, MODEL_PREFERENCE_KEY, discovered)
    except (SecretStoreError, ValueError) as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    return _gemini_keys_status(db)


@router.delete("/gemini/keys/{slot}", response_model=GeminiKeysStatus)
def remove_gemini_key_slot(slot: int, db: Session = Depends(get_db)) -> GeminiKeysStatus:
    try:
        if not 1 <= slot <= MAX_GEMINI_KEYS:
            raise HTTPException(status_code=404, detail="Key slot not found")
        value = get_gemini_key_by_slot(db, slot)
        deleted = delete_gemini_key_slot(db, slot)
        if not deleted:
            raise HTTPException(status_code=404, detail="Key slot not found")
        if value:
            SHARED_KEY_POOL.forget(value)
    except SecretStoreError as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc
    return _gemini_keys_status(db)


@router.put("/gemini/model", response_model=GeminiSettingStatus)
def save_gemini_model(
    payload: GeminiModelInput, db: Session = Depends(get_db)
) -> GeminiSettingStatus:
    requested = payload.model.strip()
    if requested not in SUPPORTED_MODEL_CANDIDATES:
        raise HTTPException(
            status_code=422,
            detail=f"Unsupported model; supported: {', '.join(SUPPORTED_MODEL_CANDIDATES)}",
        )
    set_preference(db, MODEL_PREFERENCE_KEY, requested)
    return _gemini_status(db, validated=True)


@router.post("/gemini/test", response_model=GeminiSettingStatus)
async def test_gemini_setting(db: Session = Depends(get_db)) -> GeminiSettingStatus:
    try:
        keys = resolve_gemini_api_keys(db)
    except SecretStoreError as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc
    if not keys:
        raise HTTPException(status_code=409, detail="Gemini API key is not configured")
    for key in keys:
        try:
            await validate_gemini_api_key(key)
        except TimeoutError as exc:
            raise HTTPException(
                status_code=504, detail="Google Gemini validation timed out"
            ) from exc
        except GeminiInvalidKeyError as exc:
            raise HTTPException(
                status_code=400,
                detail=(
                    f"\u2022\u2022\u2022\u2022{key[-4:]}: Google \u0627\u06cc\u0646 \u06a9\u0644\u06cc\u062f \u0631\u0627 \u0631\u062f \u06a9\u0631\u062f\u061b "
                    "\u06a9\u0644\u06cc\u062f \u0630\u062e\u06cc\u0631\u0647\u200c\u0634\u062f\u0647 \u0645\u0639\u062a\u0628\u0631 \u0646\u06cc\u0633\u062a"
                ),
            ) from exc
        except (GeminiNetworkError, ModelUnavailableError) as exc:
            raise HTTPException(
                status_code=503,
                detail="\u0633\u0631\u0648\u0631 \u0641\u0639\u0644\u06cc \u0628\u0647 \u0633\u0631\u0648\u06cc\u0633 Google \u062f\u0633\u062a\u0631\u0633\u06cc \u0646\u062f\u0627\u0631\u062f (\u0634\u0628\u06a9\u0647/TLS/proxy)",
            ) from exc
        except Exception as exc:
            raise HTTPException(
                status_code=400, detail="The configured Gemini key was rejected"
            ) from exc
        SHARED_KEY_POOL.forget(key)
    return _gemini_status(db, validated=True)


@router.delete("/gemini", response_model=GeminiSettingStatus)
def remove_gemini_setting(db: Session = Depends(get_db)) -> GeminiSettingStatus:
    try:
        for value in resolve_gemini_api_keys(db):
            SHARED_KEY_POOL.forget(value)
        delete_all_gemini_keys(db)
    except SecretStoreError as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc
    return _gemini_status(db)


# ---------------------------------------------------------------------------
# Telegram bot token
# ---------------------------------------------------------------------------


def _telegram_status(db: Session, *, validated: bool = False) -> TelegramSettingStatus:
    try:
        current = telegram_secret_status(db)
    except SecretStoreError as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc
    return TelegramSettingStatus(**current, validated=validated)


@router.get("/telegram", response_model=TelegramSettingStatus)
def get_telegram_setting(db: Session = Depends(get_db)) -> TelegramSettingStatus:
    return _telegram_status(db)


@router.put("/telegram", response_model=TelegramSettingStatus)
async def save_telegram_setting(
    payload: TelegramTokenInput,
    db: Session = Depends(get_db),
) -> TelegramSettingStatus:
    if not isinstance(payload.bot_token, str):
        raise HTTPException(status_code=422, detail="Telegram bot token must be a string")
    raw = payload.bot_token.strip()
    if not (20 <= len(raw) <= 300):
        raise HTTPException(status_code=422, detail="Telegram bot token length is invalid")
    try:
        validate_bot_token(raw)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    try:
        await telegram_get_me_with_token(raw)
    except TelegramNetworkError as exc:
        raise HTTPException(
            status_code=503,
            detail="Telegram از این سرور در دسترس نیست (شبکه/TLS/proxy)؛ توکن ذخیره نشد",
        ) from exc
    except TelegramError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except TimeoutError as exc:
        raise HTTPException(
            status_code=504, detail="Telegram did not respond in time; the token was not saved"
        ) from exc
    except Exception as exc:
        raise HTTPException(
            status_code=400, detail="Telegram rejected the bot token; it was not saved"
        ) from exc
    try:
        set_secret(db, TELEGRAM_SECRET_KEY, raw, hint=f"••••{raw[-4:]}")
    except (SecretStoreError, ValueError) as exc:
        raise HTTPException(
            status_code=500, detail=f"Could not store Telegram token: {exc}"
        ) from exc
    return _telegram_status(db, validated=True)


@router.post("/telegram/test", response_model=TelegramSettingStatus)
async def test_telegram_setting(db: Session = Depends(get_db)) -> TelegramSettingStatus:
    from ..services.secrets import resolve_telegram_bot_token

    token = resolve_telegram_bot_token(db)
    if not token:
        raise HTTPException(status_code=409, detail="Telegram bot token is not configured")
    try:
        await telegram_get_me_with_token(token)
    except TelegramNetworkError as exc:
        raise HTTPException(
            status_code=503,
            detail="Telegram از این سرور در دسترس نیست (شبکه/TLS/proxy)",
        ) from exc
    except TelegramError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except TimeoutError as exc:
        raise HTTPException(status_code=504, detail="Telegram validation timed out") from exc
    return _telegram_status(db, validated=True)


@router.delete("/telegram", response_model=TelegramSettingStatus)
def remove_telegram_setting(db: Session = Depends(get_db)) -> TelegramSettingStatus:
    delete_secret(db, TELEGRAM_SECRET_KEY)
    return _telegram_status(db)


# ---------------------------------------------------------------------------
# Non-secret runtime preferences
# ---------------------------------------------------------------------------


class ReminderWindowInput(BaseModel):
    days: int


@router.get("/reminder-window")
def get_reminder_window(db: Session = Depends(get_db)) -> dict[str, int]:
    from ..modules.personal.service import REMINDER_WINDOW_DAYS

    raw = get_preference(db, REMINDER_WINDOW_KEY)
    try:
        days = int(raw) if raw is not None else REMINDER_WINDOW_DAYS
    except ValueError:
        days = REMINDER_WINDOW_DAYS
    return {"days": days}


@router.put("/reminder-window")
def set_reminder_window(
    payload: ReminderWindowInput, db: Session = Depends(get_db)
) -> dict[str, int]:
    if not 0 <= payload.days <= 365:
        raise HTTPException(status_code=422, detail="days must be between 0 and 365")
    set_preference(db, REMINDER_WINDOW_KEY, str(payload.days))
    return {"days": payload.days}
