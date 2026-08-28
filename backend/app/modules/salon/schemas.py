from __future__ import annotations

import re
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

SalonStatus = Literal["lead", "contacted", "interested", "customer", "inactive", "do_not_contact"]


class ORMModel(BaseModel):
    model_config = ConfigDict(from_attributes=True)


class SalonCreate(BaseModel):
    name: str = Field(min_length=1, max_length=255)
    phone: str = Field(min_length=6, max_length=32)
    city: str | None = Field(default=None, max_length=100)
    address: str | None = None
    status: SalonStatus = "lead"
    notes: str | None = None
    tags: list[str] = Field(default_factory=list)

    @field_validator("name")
    @classmethod
    def name_not_blank(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("name must not be blank")
        return value.strip()

    @field_validator("phone")
    @classmethod
    def valid_phone(cls, value: str) -> str:
        normalized = value.strip()
        if not re.fullmatch(r"\+?[0-9][0-9\s()\-]{5,30}", normalized):
            raise ValueError("phone must be a valid international or local number")
        return normalized


class SalonUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=255)
    phone: str | None = Field(default=None, min_length=6, max_length=32)
    city: str | None = Field(default=None, max_length=100)
    address: str | None = None
    status: SalonStatus | None = None
    notes: str | None = None
    tags: list[str] | None = None

    @field_validator("name")
    @classmethod
    def name_not_blank(cls, value: str | None) -> str | None:
        if value is not None and not value.strip():
            raise ValueError("name must not be blank")
        return value.strip() if value else value

    @field_validator("phone")
    @classmethod
    def valid_phone(cls, value: str | None) -> str | None:
        if value is None:
            return value
        return SalonCreate.valid_phone(value)


class SalonRead(ORMModel):
    id: int
    name: str
    phone: str
    city: str | None
    address: str | None
    status: str
    notes: str | None
    tags: list[str]
    last_contact_at: datetime | None
    created_at: datetime
    updated_at: datetime


class BulkSalonImport(BaseModel):
    salons: list[dict] = Field(min_length=1, max_length=5000)


class InteractionCreate(BaseModel):
    channel: Literal["phone", "sms", "whatsapp", "email", "instagram", "in_person", "other"]
    direction: Literal["inbound", "outbound"] = "outbound"
    content: str = Field(min_length=1)
    outcome: str | None = Field(default=None, max_length=100)
    occurred_at: datetime | None = None
    next_follow_up_at: datetime | None = None

    @field_validator("content")
    @classmethod
    def content_not_blank(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("content must not be blank")
        return value.strip()


class InteractionRead(ORMModel):
    id: int
    salon_id: int
    channel: str
    direction: str
    content: str
    outcome: str | None
    occurred_at: datetime
    next_follow_up_at: datetime | None
    interaction_metadata: dict


class DailySalonPlanItem(BaseModel):
    salon: SalonRead
    days_since_contact: int | None
    cadence_days: int
    reason: str
