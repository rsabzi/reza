"""Pydantic request/response schemas for the conversational assistant."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator


class ChatRequest(BaseModel):
    message: str = Field(min_length=1, max_length=4000)
    conversation_id: int | None = None

    @field_validator("message")
    @classmethod
    def message_not_blank(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("message must not be blank")
        return value.strip()


class ActionCard(BaseModel):
    name: str
    ok: bool
    needs_approval: bool = False
    arguments: dict[str, Any] | None = None
    result: Any | None = None
    error: str | None = None
    step_id: int | None = None


class AssistantMessageRead(BaseModel):
    id: int
    role: str
    content: str
    actions: list[ActionCard] = Field(default_factory=list)
    created_at: datetime


class ChatResponse(BaseModel):
    conversation_id: int
    model: str
    message: AssistantMessageRead
    needs_approval: bool


class ConversationCreate(BaseModel):
    title: str | None = Field(default=None, max_length=255)

    @field_validator("title")
    @classmethod
    def title_not_blank(cls, value: str | None) -> str | None:
        if value is not None and not value.strip():
            return None
        return value.strip() if value else value


class ConversationRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    title: str
    status: str
    created_at: datetime
    updated_at: datetime


class ConversationSummary(BaseModel):
    id: int
    title: str
    status: str
    last_message: str | None
    message_count: int
    created_at: datetime
    updated_at: datetime


class ConversationDetail(BaseModel):
    id: int
    title: str
    status: str
    messages: list[AssistantMessageRead] = Field(default_factory=list)
    action_runs: list[dict[str, Any]] = Field(default_factory=list)
    created_at: datetime
    updated_at: datetime
