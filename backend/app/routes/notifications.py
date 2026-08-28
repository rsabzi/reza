"""Server-pushed dashboard notifications (daily brief, reminders, info)."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..database import get_db
from ..models import AppNotification, utcnow

router = APIRouter(prefix="/notifications", tags=["notifications"])


class NotificationRead(BaseModel):
    id: int
    kind: str
    title: str
    body: dict[str, Any]
    read_at: str | None = None
    created_at: str | None = None


def _serialize(item: AppNotification) -> dict[str, Any]:
    return {
        "id": item.id,
        "kind": item.kind,
        "title": item.title,
        "body": item.body or {},
        "read_at": item.read_at.isoformat() if item.read_at else None,
        "created_at": item.created_at.isoformat() if item.created_at else None,
    }


@router.get("")
def list_notifications(limit: int = 30, db: Session = Depends(get_db)) -> dict[str, Any]:
    items = list(
        db.scalars(
            select(AppNotification).order_by(AppNotification.id.desc()).limit(min(limit, 100))
        )
    )
    return {
        "notifications": [_serialize(item) for item in items],
        "unread": sum(1 for item in items if item.read_at is None),
    }


@router.post("/{notification_id}/read")
def mark_read(notification_id: int, db: Session = Depends(get_db)) -> dict[str, Any]:
    record = db.get(AppNotification, notification_id)
    if record is None:
        raise HTTPException(status_code=404, detail="Notification not found")
    if record.read_at is None:
        record.read_at = utcnow()
        db.commit()
    return _serialize(record)


@router.post("/read-all")
def mark_all_read(db: Session = Depends(get_db)) -> dict[str, int]:
    updated = 0
    for record in db.scalars(select(AppNotification).where(AppNotification.read_at.is_(None))):
        record.read_at = utcnow()
        updated += 1
    db.commit()
    return {"read": updated}
