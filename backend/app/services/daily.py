"""Daily delivery plan: staggered deadlines, morning brief, evening report.

The single user can spread pending tasks over consecutive days (one task per
day starting tomorrow). A background poller then:

- at the configured morning time (default 08:00, agent timezone) creates a
  dashboard notification listing today's deliverables and, when a Telegram
  endpoint is configured, pushes the same brief to the user's own chat;
- at the configured evening time (default 21:00) asks for the day's report,
  which the user answers in the dashboard or through the companion chat
  (``submit_daily_report`` tool).

Both notifications are deduplicated per local date, so restarts and the 30s
poller can never spam the user.
"""

from __future__ import annotations

import logging
from datetime import date, datetime, time, timedelta, timezone
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from ..models import (
    AppNotification,
    ContactEndpoint,
    DailyReport,
    OutboundMessage,
    Task,
    utcnow,
)
from ..scheduler import agent_timezone
from ..services.preferences import get_preference, set_preference
from ..services.telegram import telegram_send_message

logger = logging.getLogger("agent.daily")

DAILY_BRIEF_ENABLED_KEY = "daily_brief_enabled"
DAILY_BRIEF_MORNING_KEY = "daily_brief_morning_time"
DAILY_BRIEF_EVENING_KEY = "daily_brief_evening_time"

DEFAULT_MORNING_TIME = "08:00"
DEFAULT_EVENING_TIME = "21:00"
# A deliverable's deadline is the end of a normal workday in the local zone.
DUE_HOUR = 18


def _parse_hhmm(value: str | None, default: str) -> time:
    raw = (value or default).strip()
    try:
        hour, minute = (int(part) for part in raw.split(":"))
        return time(hour=hour, minute=minute)
    except (ValueError, TypeError):
        hour, minute = (int(part) for part in default.split(":"))
        return time(hour=hour, minute=minute)


def daily_brief_settings(db: Session) -> dict[str, Any]:
    return {
        "enabled": (get_preference(db, DAILY_BRIEF_ENABLED_KEY, "1") or "1") == "1",
        "morning_time": get_preference(db, DAILY_BRIEF_MORNING_KEY, DEFAULT_MORNING_TIME)
        or DEFAULT_MORNING_TIME,
        "evening_time": get_preference(db, DAILY_BRIEF_EVENING_KEY, DEFAULT_EVENING_TIME)
        or DEFAULT_EVENING_TIME,
        "timezone": str(agent_timezone()),
    }


def update_daily_brief_settings(
    db: Session,
    *,
    enabled: bool | None = None,
    morning_time: str | None = None,
    evening_time: str | None = None,
) -> dict[str, Any]:
    if morning_time is not None:
        _parse_hhmm(morning_time, DEFAULT_MORNING_TIME)  # validate
        set_preference(db, DAILY_BRIEF_MORNING_KEY, morning_time.strip())
    if evening_time is not None:
        _parse_hhmm(evening_time, DEFAULT_EVENING_TIME)  # validate
        set_preference(db, DAILY_BRIEF_EVENING_KEY, evening_time.strip())
    if enabled is not None:
        set_preference(db, DAILY_BRIEF_ENABLED_KEY, "1" if enabled else "0")
    return daily_brief_settings(db)


def _local_due_datetime(day: date) -> datetime:
    local = datetime.combine(day, time(hour=DUE_HOUR), tzinfo=agent_timezone())
    return local.astimezone(timezone.utc)


def _local_date_of(value: datetime) -> date:
    return value.astimezone(agent_timezone()).date()


def assign_daily_deadlines(
    db: Session,
    *,
    start_date: date | None = None,
    only_pending: bool = True,
) -> list[dict[str, Any]]:
    """Spread tasks without a deadline over consecutive days, one per day.

    Ordering is stable (oldest first) so «از فردا برای هر تسک ۱ روز» maps to
    the backlog top-down. Tasks that already have a deadline are untouched.
    """

    query = select(Task).where(Task.due_at.is_(None))
    if only_pending:
        query = query.where(Task.status == "pending")
    tasks = list(db.scalars(query.order_by(Task.id)))
    tz = agent_timezone()
    today = start_date or (datetime.now(tz).date() + timedelta(days=1))
    assigned: list[dict[str, Any]] = []
    for index, task in enumerate(tasks):
        day = today + timedelta(days=index)
        task.due_at = _local_due_datetime(day)
        assigned.append(
            {
                "task_id": task.id,
                "title": task.title,
                "due_date": day.isoformat(),
                "due_at": task.due_at.isoformat(),
            }
        )
    db.commit()
    return assigned


def tasks_due_on(db: Session, day: date) -> list[Task]:
    tz = agent_timezone()
    start = datetime.combine(day, time.min, tzinfo=tz).astimezone(timezone.utc)
    end = datetime.combine(day + timedelta(days=1), time.min, tzinfo=tz).astimezone(timezone.utc)
    return list(
        db.scalars(
            select(Task)
            .where(Task.due_at.is_not(None), Task.due_at >= start, Task.due_at < end)
            .order_by(Task.due_at)
        )
    )


def save_daily_report(db: Session, content: str, *, report_date: date | None = None) -> DailyReport:
    normalized = content.strip()
    if not normalized:
        raise ValueError("گزارش نمی‌تواند خالی باشد")
    day = report_date or datetime.now(agent_timezone()).date()
    record = db.scalar(select(DailyReport).where(DailyReport.report_date == day.isoformat()))
    if record is None:
        record = DailyReport(report_date=day.isoformat(), content=normalized)
        db.add(record)
    else:
        record.content = normalized
    db.commit()
    db.refresh(record)
    return record


def daily_report_for(db: Session, day: date) -> DailyReport | None:
    return db.scalar(select(DailyReport).where(DailyReport.report_date == day.isoformat()))


def _create_notification(
    db: Session, *, kind: str, title: str, body: dict[str, Any], dedupe_key: str
) -> AppNotification | None:
    existing = db.scalar(select(AppNotification).where(AppNotification.dedupe_key == dedupe_key))
    if existing is not None:
        return None
    notification = AppNotification(kind=kind, title=title, body=body, dedupe_key=dedupe_key)
    db.add(notification)
    db.commit()
    db.refresh(notification)
    return notification


async def _push_telegram_copy(db: Session, text: str, dedupe_key: str) -> bool:
    """Best-effort push of the brief to the user's own Telegram chat.

    These are the user's own reminders (opted in via the daily plan), so they
    are sent directly and recorded as outbound messages. Any failure is logged
    and swallowed — the dashboard notification already exists.
    """

    endpoint = db.scalar(
        select(ContactEndpoint)
        .where(
            ContactEndpoint.channel == "telegram",
            ContactEndpoint.enabled.is_(True),
            ContactEndpoint.owner_type == "general",
        )
        .order_by(ContactEndpoint.id)
    )
    if endpoint is None:
        return False
    key = f"daily-brief:{dedupe_key}"
    if db.scalar(select(OutboundMessage).where(OutboundMessage.idempotency_key == key)) is not None:
        return False
    message = OutboundMessage(
        owner_type="general",
        contact_endpoint_id=endpoint.id,
        channel="telegram",
        content=text,
        status="needs_approval",
        idempotency_key=key,
    )
    db.add(message)
    db.commit()
    try:
        provider_message_id, receipt = await telegram_send_message(
            db, chat_id=endpoint.address, text=text
        )
        message.status = "sent"
        message.provider_message_id = provider_message_id
        message.provider_response = receipt
        message.sent_at = utcnow()
        db.commit()
        return True
    except Exception as exc:
        message.status = "failed"
        message.error = str(exc)[:500]
        db.commit()
        logger.warning("daily brief telegram push failed: %s", exc)
        return False


async def push_daily_brief_notifications(db: Session) -> int:
    """Push the newest morning/evening briefs to Telegram (idempotent per date)."""

    pushed = 0
    notifications = list(
        db.scalars(
            select(AppNotification)
            .where(AppNotification.kind.in_(["morning_reminder", "evening_report"]))
            .order_by(AppNotification.id.desc())
            .limit(4)
        )
    )
    for notification in notifications:
        if notification.dedupe_key is None:
            continue
        if await _push_telegram_copy(
            db, str((notification.body or {}).get("text", "")), notification.dedupe_key
        ):
            pushed += 1
    return pushed


def _morning_text(day: date, tasks: list[Task]) -> str:
    lines = [f"☀️ کارهای امروز ({day.isoformat()}):"]
    for task in tasks:
        mark = "✅" if task.status == "done" else "⬜"
        lines.append(f"{mark} {task.title}")
    lines.append("وقت تحویل: تا پایان امروز. موفق باشی 🌟")
    return "\n".join(lines)


def _evening_text(day: date, tasks: list[Task]) -> str:
    done = sum(1 for task in tasks if task.status == "done")
    lines = [
        f"🌙 گزارش شب ({day.isoformat()}):",
        f"از {len(tasks)} کار امروز {done} تا تکمیل شده.",
        "خلاصه‌ی کاری که امروز انجام دادی را برایت ثبت کنم بنویس.",
    ]
    return "\n".join(lines)


def process_daily_brief(db: Session, *, now: datetime | None = None) -> list[AppNotification]:
    """Create today's morning/evening notifications when their time has passed.

    Called every poller tick; per-date dedupe makes it idempotent. Injectable
    ``now`` keeps the logic fully testable.
    """

    settings = daily_brief_settings(db)
    if not settings["enabled"]:
        return []
    tz = agent_timezone()
    local_now = now or utcnow()
    if local_now.tzinfo is None:
        local_now = local_now.replace(tzinfo=timezone.utc)
    local_now = local_now.astimezone(tz)
    today = local_now.date()
    created: list[AppNotification] = []

    morning_at = datetime.combine(
        today, _parse_hhmm(settings["morning_time"], DEFAULT_MORNING_TIME), tzinfo=tz
    )
    if local_now >= morning_at:
        due_tasks = tasks_due_on(db, today)
        if due_tasks:
            notification = _create_notification(
                db,
                kind="morning_reminder",
                title="یادآوری کارهای امروز",
                body={
                    "tasks": [
                        {"id": task.id, "title": task.title, "status": task.status}
                        for task in due_tasks
                    ],
                    "text": _morning_text(today, due_tasks),
                },
                dedupe_key=f"morning:{today.isoformat()}",
            )
            if notification is not None:
                created.append(notification)

    evening_at = datetime.combine(
        today, _parse_hhmm(settings["evening_time"], DEFAULT_EVENING_TIME), tzinfo=tz
    )
    if local_now >= evening_at and daily_report_for(db, today) is None:
        due_tasks = tasks_due_on(db, today)
        notification = _create_notification(
            db,
            kind="evening_report",
            title="گزارش شبانه",
            body={
                "tasks": [
                    {"id": task.id, "title": task.title, "status": task.status}
                    for task in due_tasks
                ],
                "text": _evening_text(today, due_tasks),
            },
            dedupe_key=f"evening:{today.isoformat()}",
        )
        if notification is not None:
            created.append(notification)

    return created


def daily_plan_overview(db: Session) -> dict[str, Any]:
    tz = agent_timezone()
    today = datetime.now(tz).date()
    due_today = tasks_due_on(db, today)
    return {
        "settings": daily_brief_settings(db),
        "today": [
            {
                "id": task.id,
                "title": task.title,
                "status": task.status,
                "due_at": task.due_at.isoformat() if task.due_at else None,
            }
            for task in due_today
        ],
        "unscheduled_count": len(
            list(db.scalars(select(Task).where(Task.due_at.is_(None), Task.status == "pending")))
        ),
        "report_today": (
            daily_report_for(db, today).content if daily_report_for(db, today) is not None else None
        ),
    }
