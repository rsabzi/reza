"""Generic contact endpoint API (Telegram chat ids and future channels)."""

from __future__ import annotations

from datetime import datetime
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Response, status
from pydantic import BaseModel, ConfigDict, Field, field_validator
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from ..database import get_db
from ..models import ContactEndpoint

router = APIRouter(prefix="/contacts", tags=["contacts"])

OwnerType = Literal["salon", "project", "general"]


class ContactEndpointCreate(BaseModel):
    owner_type: OwnerType
    owner_id: int | None = None
    channel: Literal["telegram"] = "telegram"
    address: str = Field(min_length=1, max_length=255)
    label: str | None = Field(default=None, max_length=255)
    enabled: bool = True

    @field_validator("address")
    @classmethod
    def address_not_blank(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("address must not be blank")
        try:
            int(value)
        except ValueError as exc:
            raise ValueError("Telegram chat_id must be numeric") from exc
        return value


class ContactEndpointUpdate(BaseModel):
    address: str | None = Field(default=None, max_length=255)
    label: str | None = Field(default=None, max_length=255)
    enabled: bool | None = None

    @field_validator("address")
    @classmethod
    def address_valid(cls, value: str | None) -> str | None:
        if value is None:
            return value
        value = value.strip()
        if not value:
            raise ValueError("address must not be blank")
        if not value.isdigit():
            raise ValueError("Telegram chat_id must be numeric")
        return value


class ContactEndpointRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    owner_type: str
    owner_id: int | None
    channel: str
    address: str
    label: str | None
    enabled: bool
    created_at: datetime
    updated_at: datetime


@router.get("", response_model=list[ContactEndpointRead])
def list_contacts(
    owner_type: str | None = None,
    owner_id: int | None = None,
    db: Session = Depends(get_db),
) -> list[ContactEndpoint]:
    statement = select(ContactEndpoint).order_by(ContactEndpoint.id)
    if owner_type:
        statement = statement.where(ContactEndpoint.owner_type == owner_type)
    if owner_id is not None:
        statement = statement.where(ContactEndpoint.owner_id == owner_id)
    return list(db.scalars(statement))


@router.post("", response_model=ContactEndpointRead, status_code=status.HTTP_201_CREATED)
def create_contact(
    payload: ContactEndpointCreate, db: Session = Depends(get_db)
) -> ContactEndpoint:
    contact = ContactEndpoint(**payload.model_dump())
    db.add(contact)
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(status_code=409, detail="This contact endpoint already exists") from exc
    db.refresh(contact)
    return contact


@router.patch("/{contact_id}", response_model=ContactEndpointRead)
def update_contact(
    contact_id: int, payload: ContactEndpointUpdate, db: Session = Depends(get_db)
) -> ContactEndpoint:
    contact = db.get(ContactEndpoint, contact_id)
    if contact is None:
        raise HTTPException(status_code=404, detail="Contact endpoint not found")
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(contact, field, value)
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(status_code=409, detail="This contact endpoint already exists") from exc
    db.refresh(contact)
    return contact


@router.delete("/{contact_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_contact(contact_id: int, db: Session = Depends(get_db)) -> Response:
    contact = db.get(ContactEndpoint, contact_id)
    if contact is None:
        raise HTTPException(status_code=404, detail="Contact endpoint not found")
    db.delete(contact)
    db.commit()
    return Response(status_code=204)
