"""Encrypted local secret storage for the single-user Agent Core."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any

from cryptography.fernet import Fernet, InvalidToken
from sqlalchemy import select
from sqlalchemy.exc import OperationalError
from sqlalchemy.orm import Session

from ..database import SessionLocal
from ..models import AppSetting

GEMINI_SECRET_KEY = "gemini_api_key"
TELEGRAM_SECRET_KEY = "telegram_bot_token"

# Multiple Gemini keys: slot 1 reuses the legacy single-key record so existing
# installations keep working without migration; further slots are stored as
# "gemini_api_key:2", "gemini_api_key:3", ...
GEMINI_KEY_SLOT_PREFIX = "gemini_api_key:"
MAX_GEMINI_KEYS = 10


def gemini_slot_setting_key(slot: int) -> str:
    if slot < 1:
        raise ValueError("slot must be >= 1")
    return GEMINI_SECRET_KEY if slot == 1 else f"{GEMINI_KEY_SLOT_PREFIX}{slot}"


class SecretStoreError(RuntimeError):
    """A local secret could not be encrypted or decrypted."""


def _master_key_path() -> Path:
    return Path(os.getenv("AGENT_MASTER_KEY_FILE", ".agent_master_key")).expanduser().resolve()


def _load_or_create_master_key() -> bytes:
    configured = os.getenv("AGENT_MASTER_KEY")
    if configured:
        key = configured.encode("utf-8")
        try:
            Fernet(key)
        except ValueError as exc:
            raise SecretStoreError("AGENT_MASTER_KEY is not a valid Fernet key") from exc
        return key

    path = _master_key_path()
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    if not path.exists():
        key = Fernet.generate_key()
        try:
            descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        except FileExistsError:
            return path.read_bytes().strip()
        with os.fdopen(descriptor, "wb") as key_file:
            key_file.write(key)
    try:
        path.chmod(0o600)
    except OSError:
        # Windows does not implement POSIX file modes; ACLs remain OS-managed.
        pass
    return path.read_bytes().strip()


def _cipher() -> Fernet:
    try:
        return Fernet(_load_or_create_master_key())
    except (ValueError, TypeError) as exc:
        raise SecretStoreError("Local master key is invalid") from exc


def set_secret(db: Session, setting_key: str, value: str, *, hint: str | None = None) -> AppSetting:
    normalized = value.strip()
    if not normalized:
        raise ValueError("Secret value must not be blank")
    encrypted = _cipher().encrypt(normalized.encode("utf-8")).decode("ascii")
    record = db.scalar(select(AppSetting).where(AppSetting.setting_key == setting_key))
    if record is None:
        record = AppSetting(setting_key=setting_key, encrypted_value=encrypted, value_hint=hint)
        db.add(record)
    else:
        record.encrypted_value = encrypted
        record.value_hint = hint
    db.commit()
    db.refresh(record)
    return record


def get_secret(db: Session, setting_key: str) -> str | None:
    record = db.scalar(select(AppSetting).where(AppSetting.setting_key == setting_key))
    if record is None:
        return None
    try:
        return _cipher().decrypt(record.encrypted_value.encode("ascii")).decode("utf-8")
    except (InvalidToken, ValueError, UnicodeError) as exc:
        raise SecretStoreError(
            "Stored secret cannot be decrypted; replace it from Dashboard settings"
        ) from exc


def delete_secret(db: Session, setting_key: str) -> bool:
    record = db.scalar(select(AppSetting).where(AppSetting.setting_key == setting_key))
    if record is None:
        return False
    db.delete(record)
    db.commit()
    return True


def environment_gemini_key() -> str | None:
    # The current Google Gen AI SDK gives GOOGLE_API_KEY precedence when both exist.
    return os.getenv("GOOGLE_API_KEY") or os.getenv("GEMINI_API_KEY")


def list_gemini_key_slots(db: Session) -> list[int]:
    """Stored Gemini key slot numbers in rotation order (1 = legacy primary)."""

    slots: list[int] = []
    for setting_key in db.scalars(select(AppSetting.setting_key)).all():
        if setting_key == GEMINI_SECRET_KEY:
            slots.append(1)
        elif setting_key.startswith(GEMINI_KEY_SLOT_PREFIX):
            suffix = setting_key.removeprefix(GEMINI_KEY_SLOT_PREFIX)
            if suffix.isdigit():
                slots.append(int(suffix))
    return sorted(slots)


def get_gemini_key_by_slot(db: Session, slot: int) -> str | None:
    return get_secret(db, gemini_slot_setting_key(slot))


def add_gemini_key(db: Session, value: str) -> int:
    """Store one more rotating Gemini key; returns its slot number."""

    normalized = value.strip()
    if not normalized:
        raise ValueError("Gemini API key must not be blank")
    if normalized in resolve_gemini_api_keys(db):
        raise ValueError("این کلید قبلاً ثبت شده است")
    slots = list_gemini_key_slots(db)
    if len(slots) >= MAX_GEMINI_KEYS:
        raise ValueError(f"حداکثر {MAX_GEMINI_KEYS} کلید Gemini می‌توان ثبت کرد")
    slot = next(candidate for candidate in range(1, MAX_GEMINI_KEYS + 1) if candidate not in slots)
    set_secret(
        db,
        gemini_slot_setting_key(slot),
        normalized,
        hint=f"••••{normalized[-4:]}",
    )
    return slot


def delete_gemini_key_slot(db: Session, slot: int) -> bool:
    return delete_secret(db, gemini_slot_setting_key(slot))


def delete_all_gemini_keys(db: Session) -> int:
    removed = 0
    for slot in list_gemini_key_slots(db):
        if delete_gemini_key_slot(db, slot):
            removed += 1
    return removed


def gemini_keys_overview(db: Session) -> list[dict[str, Any]]:
    """Slot + redacted hint for every stored Gemini key (never raw values)."""

    overview: list[dict[str, Any]] = []
    for slot in list_gemini_key_slots(db):
        record = db.scalar(
            select(AppSetting).where(AppSetting.setting_key == gemini_slot_setting_key(slot))
        )
        overview.append(
            {
                "slot": slot,
                "hint": record.value_hint if record is not None else None,
                "created_at": record.created_at if record is not None else None,
            }
        )
    return overview


def resolve_gemini_api_keys(db: Session | None = None) -> list[str]:
    """All usable Gemini keys in slot order, then the environment key as reserve."""

    def _resolve(session: Session | None) -> list[str]:
        keys: list[str] = []
        try:
            if session is not None:
                for slot in list_gemini_key_slots(session):
                    value = get_gemini_key_by_slot(session, slot)
                    if value and value not in keys:
                        keys.append(value)
        except OperationalError:
            pass  # During first boot the settings table may not exist yet.
        environment_key = environment_gemini_key()
        if environment_key and environment_key not in keys:
            keys.append(environment_key)
        return keys

    if db is not None:
        return _resolve(db)
    try:
        with SessionLocal() as session:
            return _resolve(session)
    except OperationalError:
        return _resolve(None)


def resolve_gemini_api_key(db: Session | None = None) -> str | None:
    """Prefer a Dashboard-managed key and fall back to server environment variables."""

    keys = resolve_gemini_api_keys(db)
    return keys[0] if keys else None


def iter_stored_secret_values(db: Session) -> list[str]:
    """Every stored secret value (all Gemini slots + Telegram) for redaction."""

    values: list[str] = []
    for setting_key in (gemini_slot_setting_key(slot) for slot in list_gemini_key_slots(db)):
        try:
            value = get_secret(db, setting_key)
        except SecretStoreError:
            value = None
        if value:
            values.append(value)
    try:
        token = get_secret(db, TELEGRAM_SECRET_KEY)
    except SecretStoreError:
        token = None
    if token:
        values.append(token)
    return values


def redact_stored_secrets(db: Session, text: str) -> str:
    """Replace every stored secret value appearing in text with a bullet mask."""

    redacted = text
    for value in iter_stored_secret_values(db):
        if len(value) >= 8:
            redacted = redacted.replace(value, "••••")
    return redacted


def gemini_secret_status(db: Session) -> dict[str, str | bool | None]:
    slots = list_gemini_key_slots(db)
    if slots:
        # Decrypt each slot so a missing/wrong master key is reported as not ready.
        for slot in slots:
            get_gemini_key_by_slot(db, slot)
        first = db.scalar(
            select(AppSetting).where(AppSetting.setting_key == gemini_slot_setting_key(slots[0]))
        )
        return {
            "configured": True,
            "source": "dashboard",
            "hint": first.value_hint if first is not None else None,
        }
    environment_key = environment_gemini_key()
    return {
        "configured": bool(environment_key),
        "source": "environment" if environment_key else "none",
        "hint": f"••••{environment_key[-4:]}" if environment_key else None,
    }


def telegram_secret_status(db: Session) -> dict[str, str | bool | None]:
    """Report Telegram bot configuration without ever exposing the token."""

    record = db.scalar(select(AppSetting).where(AppSetting.setting_key == TELEGRAM_SECRET_KEY))
    if record is not None:
        # Decrypt once so a missing/wrong master key is reported as not ready.
        get_secret(db, TELEGRAM_SECRET_KEY)
        return {"configured": True, "source": "dashboard", "hint": record.value_hint}
    token = os.getenv("TELEGRAM_BOT_TOKEN") or os.getenv("TELEGRAM_TOKEN") or ""
    return {
        "configured": bool(token),
        "source": "environment" if token else "none",
        "hint": f"••••{token[-4:]}" if token else None,
    }


def resolve_telegram_bot_token(db: Session | None = None) -> str | None:
    if db is not None:
        return (
            get_secret(db, TELEGRAM_SECRET_KEY)
            or os.getenv("TELEGRAM_BOT_TOKEN")
            or os.getenv("TELEGRAM_TOKEN")
        )
    try:
        with SessionLocal() as session:
            return (
                get_secret(session, TELEGRAM_SECRET_KEY)
                or os.getenv("TELEGRAM_BOT_TOKEN")
                or os.getenv("TELEGRAM_TOKEN")
            )
    except OperationalError:
        return os.getenv("TELEGRAM_BOT_TOKEN") or os.getenv("TELEGRAM_TOKEN")
