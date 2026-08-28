"""Non-sensitive runtime capability status for the local dashboard."""

from __future__ import annotations

import os

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from ..agent.ai_client import AI_MODEL
from ..database import get_db
from ..memory.embedder import EMBEDDING_MODEL
from ..scheduler import agent_timezone, scheduler_running
from ..services.secrets import SecretStoreError, gemini_secret_status

router = APIRouter(prefix="/system", tags=["system"])


@router.get("/status")
def system_status(db: Session = Depends(get_db)) -> dict[str, str | bool | None]:
    """Expose configuration readiness without ever returning credential values."""

    secret_error: str | None = None
    try:
        key_status = gemini_secret_status(db)
    except SecretStoreError as exc:
        key_status = {"configured": False, "source": "error", "hint": None}
        secret_error = str(exc)
    has_key = bool(key_status["configured"])
    configured_backend = os.getenv("EMBEDDING_BACKEND", "auto").lower()
    effective_backend = (
        "gemini"
        if configured_backend == "gemini" or (configured_backend == "auto" and has_key)
        else "local"
    )
    return {
        "service": "Agent Core",
        "version": "1.0.0",
        "api_ready": True,
        "scheduler_running": scheduler_running(),
        "gemini_configured": has_key,
        "gemini_key_source": key_status["source"],
        "gemini_key_hint": key_status["hint"],
        "secret_error": secret_error,
        "reasoning_model": AI_MODEL,
        "embedding_model": EMBEDDING_MODEL,
        "embedding_backend": effective_backend,
        "timezone": str(agent_timezone()),
        "database": "SQLite",
    }
