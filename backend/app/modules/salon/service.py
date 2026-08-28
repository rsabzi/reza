"""Salon business rules and memory integration."""

from __future__ import annotations

import re
from datetime import datetime, timezone

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from ...memory.store import add_memory
from ...models import Playbook, utcnow
from .models import Salon, SalonInteraction

DEFAULT_CADENCE_DAYS = 7


def _aware_utc(value: datetime) -> datetime:
    return (
        value.replace(tzinfo=timezone.utc)
        if value.tzinfo is None
        else value.astimezone(timezone.utc)
    )


def cadence_days_from_text(content: str, default: int = DEFAULT_CADENCE_DAYS) -> int:
    normalized = content.translate(str.maketrans("۰۱۲۳۴۵۶۷۸۹٠١٢٣٤٥٦٧٨٩", "01234567890123456789"))
    patterns = [
        r"(?:do\s+not|don't|never)\s+contact.{0,80}?(?:within|for)\s+(\d+)\s+days?",
        r"(?:cadence|follow[- ]?up).{0,50}?(\d+)\s+days?",
        r"(?:تماس|پیگیری).{0,40}?(?:تا|ظرف|هر)\s*(\d+)\s*روز",
        r"(?:تا|ظرف)\s*(\d+)\s*روز.{0,40}?(?:تماس|پیگیری)",
        r"(\d+)\s*روز.{0,40}?(?:تماس|پیگیری)",
    ]
    for pattern in patterns:
        match = re.search(pattern, normalized, flags=re.IGNORECASE | re.DOTALL)
        if match:
            value = int(match.group(1))
            if 1 <= value <= 365:
                return value
    return default


def current_cadence_days(db: Session) -> int:
    playbook = db.scalar(
        select(Playbook)
        .where(Playbook.module_name == "salon")
        .order_by(Playbook.created_at.desc(), Playbook.id.desc())
    )
    return cadence_days_from_text(playbook.content) if playbook else DEFAULT_CADENCE_DAYS


def log_interaction(
    db: Session,
    *,
    salon: Salon,
    channel: str,
    direction: str,
    content: str,
    outcome: str | None = None,
    occurred_at: datetime | None = None,
    next_follow_up_at: datetime | None = None,
    commit: bool = True,
) -> SalonInteraction:
    happened_at = occurred_at or utcnow()
    interaction = SalonInteraction(
        salon_id=salon.id,
        channel=channel,
        direction=direction,
        content=content.strip(),
        outcome=outcome,
        occurred_at=happened_at,
        next_follow_up_at=next_follow_up_at,
    )
    db.add(interaction)
    db.flush()
    salon.last_contact_at = happened_at
    add_memory(
        db,
        content=(
            f"Salon interaction with {salon.name} via {channel} ({direction}). "
            f"Content: {content.strip()}. Outcome: {outcome or 'not specified'}"
        ),
        source="salon_interaction",
        source_id=str(interaction.id),
        module_name="salon",
        metadata={
            "salon_id": salon.id,
            "interaction_id": interaction.id,
            "channel": channel,
        },
        commit=False,
    )
    if commit:
        db.commit()
        db.refresh(interaction)
    return interaction


def daily_salon_plan(
    db: Session,
    *,
    as_of: datetime | None = None,
    cadence_days: int | None = None,
) -> list[dict]:
    now = _aware_utc(as_of or utcnow())
    cadence = cadence_days if cadence_days is not None else current_cadence_days(db)
    if cadence < 1:
        raise ValueError("cadence_days must be positive")
    salons = list(
        db.scalars(
            select(Salon)
            .where(Salon.status.not_in(["inactive", "do_not_contact", "customer"]))
            .order_by(Salon.id)
        )
    )
    plan: list[dict] = []
    for salon in salons:
        latest = db.scalar(
            select(func.max(SalonInteraction.occurred_at)).where(
                SalonInteraction.salon_id == salon.id
            )
        )
        days_since: int | None = None
        if latest is not None:
            days_since = (now.date() - _aware_utc(latest).date()).days
            if days_since < cadence:
                continue
        plan.append(
            {
                "salon": salon,
                "days_since_contact": days_since,
                "cadence_days": cadence,
                "reason": (
                    "No previous interaction"
                    if days_since is None
                    else f"Last contact was {days_since} days ago"
                ),
            }
        )
    return plan
