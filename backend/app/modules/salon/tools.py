"""Salon module tools; imported by application composition, never by core."""

from __future__ import annotations

from ...tools.registry import ToolContext, register_tool
from .models import Salon
from .service import daily_salon_plan, log_interaction


@register_tool(
    "generate_outreach_script",
    "Generate a personalized Persian outreach script for a salon.",
    requires_approval=True,
)
def generate_outreach_script(
    context: ToolContext, salon_id: int, offer: str = "خدمات رشد و بازاریابی"
) -> dict[str, str | int]:
    salon = context.db.get(Salon, salon_id)
    if salon is None:
        raise ValueError(f"Salon {salon_id} not found")
    city_text = f" در {salon.city}" if salon.city else ""
    script = (
        f"سلام {salon.name} عزیز، وقت‌تون بخیر. ما برای سالن‌های زیبایی{city_text} "
        f"روی {offer} کار می‌کنیم. خوشحال می‌شیم در یک گفت‌وگوی کوتاه نیازهای شما رو بشنویم."
    )
    return {"salon_id": salon.id, "script": script}


@register_tool(
    "log_salon_interaction",
    "Record a salon interaction and save it to long-term memory.",
    requires_approval=False,
)
def log_salon_interaction(
    context: ToolContext,
    salon_id: int,
    channel: str,
    content: str,
    direction: str = "outbound",
    outcome: str | None = None,
) -> dict[str, int | str]:
    salon = context.db.get(Salon, salon_id)
    if salon is None:
        raise ValueError(f"Salon {salon_id} not found")
    interaction = log_interaction(
        context.db,
        salon=salon,
        channel=channel,
        direction=direction,
        content=content,
        outcome=outcome,
        commit=False,
    )
    return {"interaction_id": interaction.id, "salon_id": salon.id, "status": "logged"}


@register_tool(
    "daily_salon_plan",
    "List salon leads eligible for contact under the current playbook cadence.",
    requires_approval=False,
)
def daily_salon_plan_tool(context: ToolContext) -> dict[str, object]:
    plan = daily_salon_plan(context.db)
    return {
        "count": len(plan),
        "salons": [
            {
                "id": item["salon"].id,
                "name": item["salon"].name,
                "reason": item["reason"],
            }
            for item in plan
        ],
    }
