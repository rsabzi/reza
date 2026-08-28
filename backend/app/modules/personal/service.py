"""Business logic for freelance projects and reminders."""

from __future__ import annotations

from datetime import date, datetime, timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from ...scheduler import agent_timezone
from .models import PersonalProject

REMINDER_WINDOW_DAYS = 3
TERMINAL_STATUSES = {"won", "lost", "completed"}
ALLOWED_TRANSITIONS: dict[str, set[str]] = {
    "lead": {"active", "lost", "paused"},
    "active": {"submitted", "completed", "lost", "paused"},
    "submitted": {"active", "won", "lost", "paused"},
    "paused": {"active", "lost"},
    "won": set(),
    "lost": set(),
    "completed": set(),
}


class InvalidStatusTransition(ValueError):
    pass


def validate_status_transition(current: str, target: str) -> None:
    if current == target:
        return
    if target not in ALLOWED_TRANSITIONS.get(current, set()):
        raise InvalidStatusTransition(f"Cannot transition project from '{current}' to '{target}'")


def daily_personal_reminder(
    db: Session,
    *,
    today: date | None = None,
    within_days: int = REMINDER_WINDOW_DAYS,
) -> list[dict]:
    if within_days < 0 or within_days > 365:
        raise ValueError("within_days must be between 0 and 365")
    start = today or datetime.now(agent_timezone()).date()
    end = start + timedelta(days=within_days)
    projects = list(
        db.scalars(
            select(PersonalProject)
            .where(
                PersonalProject.due_date.is_not(None),
                PersonalProject.due_date >= start,
                PersonalProject.due_date <= end,
                PersonalProject.status.not_in(TERMINAL_STATUSES),
            )
            .order_by(PersonalProject.due_date, PersonalProject.id)
        )
    )
    return [
        {"project": project, "days_until_due": (project.due_date - start).days}
        for project in projects
    ]
