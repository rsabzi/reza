"""Encrypted local secret storage for the single-user Agent Core."""

from __future__ import annotations

import os
from pathlib import Path

from cryptography.fernet import Fernet, InvalidToken
from sqlalchemy import select
from sqlalchemy.exc import OperationalError
from sqlalchemy.orm import Session

from ..database import SessionLocal
from ..models import AppSetting

GEMINI_SECRET_KEY = "gemini_api_key"


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


def resolve_gemini_api_key(db: Session | None = None) -> str | None:
    """Prefer a Dashboard-managed key and fall back to server environment variables."""

    if db is not None:
        return get_secret(db, GEMINI_SECRET_KEY) or environment_gemini_key()
    try:
        with SessionLocal() as session:
            return get_secret(session, GEMINI_SECRET_KEY) or environment_gemini_key()
    except OperationalError:
        # During first boot the settings table may not exist yet.
        return environment_gemini_key()


def gemini_secret_status(db: Session) -> dict[str, str | bool | None]:
    record = db.scalar(select(AppSetting).where(AppSetting.setting_key == GEMINI_SECRET_KEY))
    if record is not None:
        # Decrypt once so a missing/wrong master key is reported as not ready.
        get_secret(db, GEMINI_SECRET_KEY)
        return {"configured": True, "source": "dashboard", "hint": record.value_hint}
    environment_key = environment_gemini_key()
    return {
        "configured": bool(environment_key),
        "source": "environment" if environment_key else "none",
        "hint": f"••••{environment_key[-4:]}" if environment_key else None,
    }
