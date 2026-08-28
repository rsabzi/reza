"""Personal/freelance module persistence models."""

from __future__ import annotations

from datetime import date
from decimal import Decimal

from sqlalchemy import CheckConstraint, Date, Integer, Numeric, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from ...database import Base
from ...models import TimestampMixin


class PersonalProject(TimestampMixin, Base):
    __tablename__ = "personal_projects"
    __table_args__ = (
        CheckConstraint("budget IS NULL OR budget >= 0", name="ck_project_budget_nonnegative"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    title: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    client_name: Mapped[str | None] = mapped_column(String(255), index=True)
    description: Mapped[str | None] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(32), default="lead", nullable=False, index=True)
    due_date: Mapped[date | None] = mapped_column(Date, index=True)
    budget: Mapped[Decimal | None] = mapped_column(Numeric(12, 2))
    next_action: Mapped[str | None] = mapped_column(Text)
    external_url: Mapped[str | None] = mapped_column(String(1000))
