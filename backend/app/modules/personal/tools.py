"""Personal module tools."""

from __future__ import annotations

from ...tools.registry import ToolContext, register_tool
from .models import PersonalProject
from .service import REMINDER_WINDOW_DAYS, daily_personal_reminder


@register_tool(
    "draft_project_proposal",
    "Draft a freelance project proposal for review before use.",
    requires_approval=True,
)
def draft_project_proposal(
    context: ToolContext, project_id: int, approach: str | None = None
) -> dict[str, int | str]:
    project = context.db.get(PersonalProject, project_id)
    if project is None:
        raise ValueError(f"Personal project {project_id} not found")
    client = project.client_name or "کارفرمای محترم"
    approach_text = approach or project.next_action or "تحویل مرحله‌ای، شفاف و قابل‌اندازه‌گیری"
    proposal = (
        f"سلام {client}،\n\n"
        f"برای پروژه «{project.title}» پیشنهاد می‌کنم با رویکرد {approach_text} پیش برویم. "
        "پس از تأیید محدوده، زمان‌بندی و خروجی هر مرحله را دقیق ثبت می‌کنم.\n\n"
        "با احترام"
    )
    return {"project_id": project.id, "proposal": proposal}


@register_tool(
    "daily_personal_reminder",
    "List active personal projects due in the next three days.",
    requires_approval=False,
)
def daily_personal_reminder_tool(context: ToolContext) -> dict[str, object]:
    reminders = daily_personal_reminder(context.db, within_days=REMINDER_WINDOW_DAYS)
    return {
        "window_days": REMINDER_WINDOW_DAYS,
        "count": len(reminders),
        "projects": [
            {
                "id": item["project"].id,
                "title": item["project"].title,
                "days_until_due": item["days_until_due"],
            }
            for item in reminders
        ],
    }
