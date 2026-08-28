"""Non-sensitive runtime capability status for the local dashboard."""

from __future__ import annotations

import os

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from ..agent.ai_client import (
    DEFAULT_GEMINI_MODEL,
    SUPPORTED_MODEL_CANDIDATES,
    default_model_from_env,
)
from ..database import get_db
from ..memory.embedder import EMBEDDING_MODEL
from ..scheduler import agent_timezone, scheduler_running
from ..services.preferences import resolved_model_name
from ..services.secrets import SecretStoreError, gemini_secret_status, telegram_secret_status

router = APIRouter(prefix="/system", tags=["system"])


@router.get("/status")
def system_status(db: Session = Depends(get_db)) -> dict[str, object]:
    """Expose configuration readiness without ever returning credential values."""

    secret_error: str | None = None
    try:
        key_status = gemini_secret_status(db)
    except SecretStoreError as exc:
        key_status = {"configured": False, "source": "error", "hint": None}
        secret_error = str(exc)
    has_key = bool(key_status["configured"])
    try:
        telegram_status = telegram_secret_status(db)
    except SecretStoreError:
        telegram_status = {"configured": False, "source": "error", "hint": None}
    configured_backend = os.getenv("EMBEDDING_BACKEND", "auto").lower()
    effective_backend = (
        "gemini"
        if configured_backend == "gemini" or (configured_backend == "auto" and has_key)
        else "local"
    )
    return {
        "service": "Agent Core",
        "version": "2.0.0",
        "api_ready": True,
        "scheduler_running": scheduler_running(),
        "gemini_configured": has_key,
        "gemini_key_source": key_status["source"],
        "gemini_key_hint": key_status["hint"],
        "telegram_configured": bool(telegram_status.get("configured")),
        "secret_error": secret_error,
        "reasoning_model": resolved_model_name(db, default_model_from_env()),
        "default_model": DEFAULT_GEMINI_MODEL,
        "supported_models": list(SUPPORTED_MODEL_CANDIDATES),
        "embedding_model": EMBEDDING_MODEL,
        "embedding_backend": effective_backend,
        "timezone": str(agent_timezone()),
        "database": "SQLite",
    }
