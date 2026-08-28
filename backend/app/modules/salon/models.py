"""Salon module persistence models (kept outside Agent Core)."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from sqlalchemy import JSON, DateTime, ForeignKey, Index, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from ...database import Base
from ...models import TimestampMixin, utcnow


class Salon(TimestampMixin, Base):
    __tablename__ = "salons"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    phone: Mapped[str] = mapped_column(String(32), nullable=False, unique=True, index=True)
    city: Mapped[str | None] = mapped_column(String(100), index=True)
    address: Mapped[str | None] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(32), default="lead", nullable=False, index=True)
    notes: Mapped[str | None] = mapped_column(Text)
    tags: Mapped[list[str]] = mapped_column(JSON, default=list, nullable=False)
    last_contact_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    interactions: Mapped[list[SalonInteraction]] = relationship(
        back_populates="salon",
        cascade="all, delete-orphan",
        order_by="SalonInteraction.occurred_at",
    )


class SalonInteraction(Base):
    __tablename__ = "salon_interactions"
    __table_args__ = (Index("ix_salon_interactions_salon_occurred", "salon_id", "occurred_at"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    salon_id: Mapped[int] = mapped_column(
        ForeignKey("salons.id", ondelete="CASCADE"), nullable=False
    )
    channel: Mapped[str] = mapped_column(String(32), nullable=False)
    direction: Mapped[str] = mapped_column(String(16), default="outbound", nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    outcome: Mapped[str | None] = mapped_column(String(100))
    occurred_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, nullable=False
    )
    next_follow_up_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    interaction_metadata: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict, nullable=False)

    salon: Mapped[Salon] = relationship(back_populates="interactions")
