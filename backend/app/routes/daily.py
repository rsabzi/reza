"""Daily delivery plan API: staggered deadlines, brief settings, evening report."""

from __future__ import annotations

import logging
from datetime import datetime
from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..database import get_db
from ..models import DailyReport
from ..scheduler import agent_timezone
from ..services.daily import (
    assign_daily_deadlines,
    daily_plan_overview,
    save_daily_report,
    update_daily_brief_settings,
)

logger = logging.getLogger("agent.daily")
router = APIRouter(prefix="/daily", tags=["daily"])


class DailySettingsInput(BaseModel):
    enabled: bool | None = None
    morning_time: str | None = None
    evening_time: str | None = None


class DailyReportInput(BaseModel):
    content: str
    date: str | None = None


def _parse_report_date(value: str | None):
    if value is None:
        return None
    try:
        return datetime.fromisoformat(value).date()
    except ValueError as exc:
        raise HTTPException(status_code=422, detail="date must be YYYY-MM-DD") from exc


@router.get("/plan")
def get_daily_plan(db: Session = Depends(get_db)) -> dict[str, Any]:
    return daily_plan_overview(db)


@router.put("/settings")
def put_daily_settings(
    payload: DailySettingsInput, db: Session = Depends(get_db)
) -> dict[str, Any]:
    for field in ("morning_time", "evening_time"):
        value = getattr(payload, field)
        if value is None:
            continue
        parts = value.strip().split(":")
        valid = len(parts) == 2 and all(part.isdigit() for part in parts)
        if valid:
            hour, minute = (int(part) for part in parts)
            valid = 0 <= hour <= 23 and 0 <= minute <= 59
        if not valid:
            raise HTTPException(status_code=422, detail=f"{field} must be a valid HH:MM time")
    try:
        settings = update_daily_brief_settings(
            db,
            enabled=payload.enabled,
            morning_time=payload.morning_time,
            evening_time=payload.evening_time,
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return settings


@router.post("/deadlines/assign")
def assign_deadlines(db: Session = Depends(get_db)) -> dict[str, Any]:
    """Spread unassigned pending tasks one-per-day starting tomorrow."""

    assigned = assign_daily_deadlines(db)
    return {"assigned": assigned, "count": len(assigned)}


@router.post("/report", response_model_exclude_none=True)
def submit_report(payload: DailyReportInput, db: Session = Depends(get_db)) -> dict[str, Any]:
    try:
        record = save_daily_report(
            db, payload.content, report_date=_parse_report_date(payload.date)
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return {
        "id": record.id,
        "report_date": record.report_date,
        "content": record.content,
        "created_at": record.created_at,
    }


@router.get("/reports")
def list_reports(limit: int = 14, db: Session = Depends(get_db)) -> list[dict[str, Any]]:
    today = datetime.now(agent_timezone()).date()
    records = list(
        db.scalars(
            select(DailyReport).order_by(DailyReport.report_date.desc()).limit(min(limit, 90))
        )
    )
    return [
        {
            "id": record.id,
            "report_date": record.report_date,
            "content": record.content,
            "is_today": record.report_date == today.isoformat(),
        }
        for record in records
    ]
