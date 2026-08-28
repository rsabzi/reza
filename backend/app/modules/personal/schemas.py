from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

ProjectStatus = Literal["lead", "active", "submitted", "won", "lost", "completed", "paused"]


class ORMModel(BaseModel):
    model_config = ConfigDict(from_attributes=True)


class ProjectCreate(BaseModel):
    title: str = Field(min_length=1, max_length=255)
    client_name: str | None = Field(default=None, max_length=255)
    description: str | None = None
    status: ProjectStatus = "lead"
    due_date: date | None = None
    budget: Decimal | None = Field(default=None, ge=0, max_digits=12, decimal_places=2)
    next_action: str | None = None
    external_url: str | None = Field(default=None, max_length=1000)

    @field_validator("title")
    @classmethod
    def title_not_blank(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("title must not be blank")
        return value.strip()


class ProjectUpdate(BaseModel):
    title: str | None = Field(default=None, min_length=1, max_length=255)
    client_name: str | None = Field(default=None, max_length=255)
    description: str | None = None
    status: ProjectStatus | None = None
    due_date: date | None = None
    budget: Decimal | None = Field(default=None, ge=0, max_digits=12, decimal_places=2)
    next_action: str | None = None
    external_url: str | None = Field(default=None, max_length=1000)

    @field_validator("title")
    @classmethod
    def title_not_blank(cls, value: str | None) -> str | None:
        if value is not None and not value.strip():
            raise ValueError("title must not be blank")
        return value.strip() if value else value


class ProjectRead(ORMModel):
    id: int
    title: str
    client_name: str | None
    description: str | None
    status: str
    due_date: date | None
    budget: Decimal | None
    next_action: str | None
    external_url: str | None
    created_at: datetime
    updated_at: datetime


class ReminderItem(BaseModel):
    project: ProjectRead
    days_until_due: int
