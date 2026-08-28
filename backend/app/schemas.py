"""Pydantic request and response schemas for core resources."""

from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

TaskStatus = Literal["pending", "planned", "running", "paused", "done", "failed", "cancelled"]
StepStatus = Literal[
    "pending",
    "running",
    "needs_approval",
    "waiting_for_user",
    "done",
    "failed",
    "cancelled",
]


class ORMModel(BaseModel):
    model_config = ConfigDict(from_attributes=True)


class TaskCreate(BaseModel):
    title: str = Field(min_length=1, max_length=255)
    description: str | None = None
    status: TaskStatus = "pending"
    module_name: str | None = Field(default=None, max_length=64)
    recurrence_rule: Literal["daily"] | None = None
    scheduled_time: str | None = None

    @field_validator("title")
    @classmethod
    def title_must_not_be_blank(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("title must not be blank")
        return value

    @field_validator("scheduled_time")
    @classmethod
    def valid_time(cls, value: str | None) -> str | None:
        if value is None:
            return value
        import re

        if not re.fullmatch(r"(?:[01]\d|2[0-3]):[0-5]\d", value):
            raise ValueError("scheduled_time must use HH:MM (24-hour) format")
        return value

    @model_validator(mode="after")
    def recurrence_has_time(self) -> TaskCreate:
        if self.recurrence_rule and not self.scheduled_time:
            raise ValueError("scheduled_time is required for recurring tasks")
        return self


class TaskUpdate(BaseModel):
    title: str | None = Field(default=None, min_length=1, max_length=255)
    description: str | None = None
    status: TaskStatus | None = None
    module_name: str | None = Field(default=None, max_length=64)
    recurrence_rule: Literal["daily"] | None = None
    scheduled_time: str | None = None

    @field_validator("title")
    @classmethod
    def title_must_not_be_blank(cls, value: str | None) -> str | None:
        if value is not None and not value.strip():
            raise ValueError("title must not be blank")
        return value.strip() if value else value

    @field_validator("scheduled_time")
    @classmethod
    def valid_time(cls, value: str | None) -> str | None:
        if value is None:
            return value
        import re

        if not re.fullmatch(r"(?:[01]\d|2[0-3]):[0-5]\d", value):
            raise ValueError("scheduled_time must use HH:MM (24-hour) format")
        return value


class TaskRead(ORMModel):
    id: int
    title: str
    description: str | None
    status: str
    module_name: str | None
    parent_task_id: int | None
    recurrence_rule: str | None
    scheduled_time: str | None
    last_scheduled_at: datetime | None
    created_at: datetime
    updated_at: datetime


class StepCreate(BaseModel):
    task_id: int
    title: str = Field(min_length=1, max_length=255)
    description: str | None = None
    position: int = Field(ge=0)
    status: StepStatus = "pending"
    tool_name: str | None = Field(default=None, max_length=100)
    arguments: dict[str, Any] = Field(default_factory=dict)
    requires_approval: bool = False

    @field_validator("title")
    @classmethod
    def title_must_not_be_blank(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("title must not be blank")
        return value.strip()


class StepUpdate(BaseModel):
    title: str | None = Field(default=None, min_length=1, max_length=255)
    description: str | None = None
    position: int | None = Field(default=None, ge=0)
    status: StepStatus | None = None
    tool_name: str | None = Field(default=None, max_length=100)
    arguments: dict[str, Any] | None = None
    result: Any | None = None
    error: str | None = None
    requires_approval: bool | None = None


class StepRead(ORMModel):
    id: int
    task_id: int
    title: str
    description: str | None
    position: int
    status: str
    tool_name: str | None
    arguments: dict[str, Any]
    result: Any | None
    error: str | None
    requires_approval: bool
    approved_at: datetime | None
    created_at: datetime
    updated_at: datetime


class TaskDetail(TaskRead):
    steps: list[StepRead] = Field(default_factory=list)
