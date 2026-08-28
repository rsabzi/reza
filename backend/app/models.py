"""Core SQLAlchemy models for Agent Core."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, ClassVar

from sqlalchemy import (
    JSON,
    Boolean,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .database import Base


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class TimestampMixin:
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, onupdate=utcnow, nullable=False
    )


class Task(TimestampMixin, Base):
    __tablename__ = "tasks"
    __table_args__: ClassVar[dict[str, bool]] = {"sqlite_autoincrement": True}

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(32), default="pending", nullable=False, index=True)
    module_name: Mapped[str | None] = mapped_column(String(64), index=True)
    parent_task_id: Mapped[int | None] = mapped_column(
        ForeignKey("tasks.id", ondelete="SET NULL"), nullable=True, index=True
    )
    recurrence_rule: Mapped[str | None] = mapped_column(String(32))
    scheduled_time: Mapped[str | None] = mapped_column(String(5))
    last_scheduled_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    steps: Mapped[list[Step]] = relationship(
        back_populates="task", cascade="all, delete-orphan", order_by="Step.position"
    )
    parent_task: Mapped[Task | None] = relationship(remote_side="Task.id", uselist=False)


class Step(TimestampMixin, Base):
    __tablename__ = "steps"
    __table_args__ = (
        UniqueConstraint("task_id", "position", name="uq_step_task_position"),
        Index("ix_steps_task_status", "task_id", "status"),
        {"sqlite_autoincrement": True},
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    task_id: Mapped[int] = mapped_column(ForeignKey("tasks.id", ondelete="CASCADE"), nullable=False)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    position: Mapped[int] = mapped_column(Integer, nullable=False)
    status: Mapped[str] = mapped_column(String(32), default="pending", nullable=False, index=True)
    tool_name: Mapped[str | None] = mapped_column(String(100))
    arguments: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict, nullable=False)
    result: Mapped[Any | None] = mapped_column(JSON)
    error: Mapped[str | None] = mapped_column(Text)
    requires_approval: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    approved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    task: Mapped[Task] = relationship(back_populates="steps")


class Tool(TimestampMixin, Base):
    __tablename__ = "tools"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(100), unique=True, nullable=False, index=True)
    description: Mapped[str] = mapped_column(Text, default="", nullable=False)
    requires_approval: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    enabled: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)


class Permission(TimestampMixin, Base):
    __tablename__ = "permissions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    tool_id: Mapped[int] = mapped_column(ForeignKey("tools.id", ondelete="CASCADE"), nullable=False)
    action: Mapped[str] = mapped_column(String(64), default="execute", nullable=False)
    allowed: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)


class AppSetting(TimestampMixin, Base):
    """Encrypted server-side setting; values are never serialized to clients."""

    __tablename__ = "app_settings"
    __table_args__: ClassVar[dict[str, bool]] = {"sqlite_autoincrement": True}

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    setting_key: Mapped[str] = mapped_column(String(100), unique=True, nullable=False, index=True)
    encrypted_value: Mapped[str] = mapped_column(Text, nullable=False)
    value_hint: Mapped[str | None] = mapped_column(String(16))


class AILog(Base):
    __tablename__ = "ai_logs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    task_id: Mapped[int | None] = mapped_column(
        ForeignKey("tasks.id", ondelete="SET NULL"), index=True
    )
    operation: Mapped[str] = mapped_column(String(64), nullable=False)
    model: Mapped[str] = mapped_column(String(100), nullable=False)
    prompt: Mapped[str] = mapped_column(Text, nullable=False)
    response: Mapped[str | None] = mapped_column(Text)
    error: Mapped[str | None] = mapped_column(Text)
    attempt: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, nullable=False
    )


class Module(TimestampMixin, Base):
    __tablename__ = "modules"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    display_name: Mapped[str] = mapped_column(String(100), nullable=False)
    enabled: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    config: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict, nullable=False)


class MemoryEntry(Base):
    __tablename__ = "memory_entries"
    __table_args__ = (Index("ix_memory_source_id", "source", "source_id"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    source: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    source_id: Mapped[str | None] = mapped_column(String(100), index=True)
    module_name: Mapped[str | None] = mapped_column(String(64), index=True)
    embedding: Mapped[list[float]] = mapped_column(JSON, nullable=False)
    entry_metadata: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, nullable=False
    )


class Playbook(TimestampMixin, Base):
    __tablename__ = "playbooks"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    module_name: Mapped[str | None] = mapped_column(String(64), index=True)
