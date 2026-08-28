"""Outbound message status and provider receipts (never exposes secrets)."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, ConfigDict
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..database import get_db
from ..models import OutboundMessage

router = APIRouter(prefix="/outbound-messages", tags=["outbound"])


class OutboundMessageRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    owner_type: str | None
    owner_id: int | None
    contact_endpoint_id: int | None
    channel: str
    content: str
    status: str
    provider_message_id: str | None
    provider_response: dict[str, Any] | None
    error: str | None
    sent_at: datetime | None
    created_at: datetime
    updated_at: datetime


@router.get("", response_model=list[OutboundMessageRead])
def list_outbound_messages(
    msg_status: str | None = Query(default=None, alias="status"),
    owner_type: str | None = None,
    db: Session = Depends(get_db),
) -> list[OutboundMessage]:
    statement = select(OutboundMessage).order_by(OutboundMessage.created_at.desc()).limit(200)
    if msg_status:
        statement = statement.where(OutboundMessage.status == msg_status)
    if owner_type:
        statement = statement.where(OutboundMessage.owner_type == owner_type)
    return list(db.scalars(statement))


@router.get("/{message_id}", response_model=OutboundMessageRead)
def get_outbound_message(message_id: int, db: Session = Depends(get_db)) -> OutboundMessage:
    message = db.get(OutboundMessage, message_id)
    if message is None:
        raise HTTPException(status_code=404, detail="Outbound message not found")
    return message
