"""Secure, server-side runtime settings managed from the local dashboard."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, SecretStr
from sqlalchemy.orm import Session

from ..agent.ai_client import (
    SUPPORTED_MODEL_CANDIDATES,
    default_model_from_env,
)
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
    TELEGRAM_SECRET_KEY,
    SecretStoreError,
    delete_secret,
    gemini_secret_status,
    resolve_gemini_api_key,
    set_secret,
    telegram_secret_status,
)
from ..services.telegram import (
    TelegramError,
    telegram_get_me_with_token,
    validate_bot_token,
)

router = APIRouter(prefix="/settings", tags=["settings"])


class GeminiKeyInput(BaseModel):
    api_key: SecretStr


class GeminiModelInput(BaseModel):
    model: str


class GeminiSettingStatus(BaseModel):
    configured: bool
    source: str
    hint: str | None
    validated: bool = False
    model: str
    models: list[str]


class TelegramTokenInput(BaseModel):
    bot_token: SecretStr


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
    api_key = payload.api_key.get_secret_value().strip()
    if not 10 <= len(api_key) <= 500:
        raise HTTPException(status_code=422, detail="Gemini API key length is invalid")
    try:
        discovered = await validate_gemini_api_key(api_key)
    except TimeoutError as exc:
        raise HTTPException(
            status_code=status.HTTP_504_GATEWAY_TIMEOUT,
            detail="Google Gemini did not respond in time; the key was not saved",
        ) from exc
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Google rejected the Gemini key or the service is unreachable; the key was not saved",
        ) from exc

    try:
        set_secret(
            db,
            GEMINI_SECRET_KEY,
            api_key,
            hint=f"••••{api_key[-4:]}",
        )
        model_status = _gemini_status(db, validated=True).model_dump()
        model_status["model"] = discovered
        if get_preference(db, MODEL_PREFERENCE_KEY) is None:
            set_preference(db, MODEL_PREFERENCE_KEY, discovered)
            model_status["model"] = discovered
        return GeminiSettingStatus(**model_status)
    except (SecretStoreError, ValueError) as exc:
        raise HTTPException(status_code=500, detail=f"Could not store Gemini key: {exc}") from exc


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
        api_key = resolve_gemini_api_key(db)
    except SecretStoreError as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc
    if not api_key:
        raise HTTPException(status_code=409, detail="Gemini API key is not configured")
    try:
        await validate_gemini_api_key(api_key)
    except TimeoutError as exc:
        raise HTTPException(status_code=504, detail="Google Gemini validation timed out") from exc
    except Exception as exc:
        raise HTTPException(
            status_code=400, detail="The configured Gemini key was rejected"
        ) from exc
    return _gemini_status(db, validated=True)


@router.delete("/gemini", response_model=GeminiSettingStatus)
def remove_gemini_setting(db: Session = Depends(get_db)) -> GeminiSettingStatus:
    delete_secret(db, GEMINI_SECRET_KEY)
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
    raw = payload.bot_token.get_secret_value().strip()
    if not (20 <= len(raw) <= 300):
        raise HTTPException(status_code=422, detail="Telegram bot token length is invalid")
    try:
        validate_bot_token(raw)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    try:
        await telegram_get_me_with_token(raw)
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
