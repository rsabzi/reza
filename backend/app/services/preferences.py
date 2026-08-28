"""Non-secret server-side preferences (model choice, reminder window, ...)."""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from ..models import AppPreference

MODEL_PREFERENCE_KEY = "gemini_model"
REMINDER_WINDOW_KEY = "reminder_window_days"


def get_preference(db: Session, key: str, default: str | None = None) -> str | None:
    record = db.scalar(select(AppPreference).where(AppPreference.preference_key == key))
    if record is None:
        return default
    return record.value


def set_preference(db: Session, key: str, value: str) -> AppPreference:
    """Persist a preference; empty value removes the override and returns the default."""

    normalized = value.strip()
    record = db.scalar(select(AppPreference).where(AppPreference.preference_key == key))
    if not normalized:
        if record is not None:
            db.delete(record)
            db.commit()
        return record  # type: ignore[return-value]
    if record is None:
        record = AppPreference(preference_key=key, value=normalized)
        db.add(record)
    else:
        record.value = normalized
    db.commit()
    db.refresh(record)
    return record


def resolved_model_name(db: Session, default: str) -> str:
    return get_preference(db, MODEL_PREFERENCE_KEY, default) or default


def resolved_reminder_window_days(db: Session, default: int) -> int:
    raw = get_preference(db, REMINDER_WINDOW_KEY)
    if raw is None:
        return default
    try:
        value = int(raw)
    except ValueError:
        return default
    return value if 0 <= value <= 365 else default
