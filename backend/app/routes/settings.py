"""Secure, server-side runtime settings managed from the local dashboard."""

from __future__ import annotations

import asyncio

from fastapi import APIRouter, Depends, HTTPException, status
from google import genai
from pydantic import BaseModel, SecretStr
from sqlalchemy.orm import Session

from ..agent.ai_client import AI_MODEL
from ..database import get_db
from ..services.secrets import (
    GEMINI_SECRET_KEY,
    SecretStoreError,
    delete_secret,
    gemini_secret_status,
    resolve_gemini_api_key,
    set_secret,
)

router = APIRouter(prefix="/settings/gemini", tags=["settings"])


class GeminiKeyInput(BaseModel):
    api_key: SecretStr


class GeminiSettingStatus(BaseModel):
    configured: bool
    source: str
    hint: str | None
    validated: bool = False
    model: str = AI_MODEL


async def validate_gemini_api_key(api_key: str) -> str:
    """Validate against Google's model API without generating billable content."""

    client = genai.Client(api_key=api_key)
    try:
        model = await asyncio.wait_for(client.aio.models.get(model=AI_MODEL), timeout=15)
        return model.name or AI_MODEL
    finally:
        await client.aio.aclose()


def _status(db: Session, *, validated: bool = False) -> GeminiSettingStatus:
    try:
        current = gemini_secret_status(db)
    except SecretStoreError as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc
    return GeminiSettingStatus(**current, validated=validated, model=AI_MODEL)


@router.get("", response_model=GeminiSettingStatus)
def get_gemini_setting(db: Session = Depends(get_db)) -> GeminiSettingStatus:
    return _status(db)


@router.put("", response_model=GeminiSettingStatus)
async def save_gemini_setting(
    payload: GeminiKeyInput,
    db: Session = Depends(get_db),
) -> GeminiSettingStatus:
    api_key = payload.api_key.get_secret_value().strip()
    if not 10 <= len(api_key) <= 500:
        raise HTTPException(
            status_code=422,
            detail="Gemini API key length is invalid",
        )
    try:
        await validate_gemini_api_key(api_key)
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
    except (SecretStoreError, ValueError) as exc:
        raise HTTPException(status_code=500, detail=f"Could not store Gemini key: {exc}") from exc
    return _status(db, validated=True)


@router.post("/test", response_model=GeminiSettingStatus)
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
    return _status(db, validated=True)


@router.delete("", response_model=GeminiSettingStatus)
def remove_gemini_setting(db: Session = Depends(get_db)) -> GeminiSettingStatus:
    delete_secret(db, GEMINI_SECRET_KEY)
    return _status(db)
