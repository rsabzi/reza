"""Lightweight Persian/English time and date references used by assistant tools."""

from __future__ import annotations

import re
from datetime import date, datetime, timedelta

from ..scheduler import agent_timezone

PERSIAN_DIGITS = str.maketrans("۰۱۲۳۴۵۶۷۸۹٠١٢٣٤٥٦٧٨٩", "01234567890123456789")

WEEKDAYS: dict[str, int] = {
    "دوشنبه": 0,
    "سه‌شنبه": 1,
    "چهارشنبه": 2,
    "پنج‌شنبه": 3,
    "جمعه": 4,
    "شنبه": 5,
    "یکشنبه": 6,
    "mon": 0,
    "tue": 1,
    "wed": 2,
    "thu": 3,
    "fri": 4,
    "sat": 5,
    "sun": 6,
}


def normalize_digits(value: str) -> str:
    return value.translate(PERSIAN_DIGITS)


def parse_clock(value: str | None) -> str | None:
    """Return normalized HH:MM (24h) or None when no clock reference is present."""

    if not value:
        return None
    text = normalize_digits(value.strip())
    match = re.search(r"(?<!\d)([01]?\d|2[0-3])[:.]([0-5]\d)(?!\d)", text)
    if match:
        hour, minute = int(match.group(1)), int(match.group(2))
        return f"{hour:02d}:{minute:02d}"
    match = re.search(r"(?<!\d)([01]?\d|2[0-3])(?!\d)", text)
    if not match:
        return None
    hour = int(match.group(1))
    if not 0 <= hour <= 23:
        return None
    if "بعدازظهر" in text or "عصر" in text or "ب.ظ" in text:
        if 1 <= hour <= 11:
            hour += 12
    elif "شب" in text:
        if 1 <= hour <= 9:
            hour += 12
    elif "ظهر" in text and hour == 12:
        hour = 12
    elif "نیمه‌شب" in text and hour == 12:
        hour = 0
    return f"{hour:02d}:00"


def parse_relative_date(value: str | None) -> date | None:
    """Resolve today/future weekday references into an ISO date in the agent timezone."""

    if not value:
        return None
    text = normalize_digits(value.strip()).lower()
    today = datetime.now(agent_timezone()).date()
    if "پس‌فردا" in text or "day after tomorrow" in text:
        return today + timedelta(days=2)
    if "فردا" in text or "tomorrow" in text:
        return today + timedelta(days=1)
    iso = re.search(r"\b(\d{4})-(\d{2})-(\d{2})\b", text)
    if iso:
        try:
            return date(int(iso.group(1)), int(iso.group(2)), int(iso.group(3)))
        except ValueError:
            return None
    for label, index in WEEKDAYS.items():
        if label in text:
            delta = (index - today.weekday()) % 7
            target = today + timedelta(days=delta)
            return target
    return None


def parse_hour_minute(value: str | None, fallback: str | None = None) -> str | None:
    return parse_clock(value) or parse_clock(fallback)


def current_date_iso() -> str:
    return datetime.now(agent_timezone()).date().isoformat()
