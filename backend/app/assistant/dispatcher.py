"""Function-call dispatcher: allowlist, validation, idempotency and approval gating."""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from ..models import AgentActionRun, Step, Task, utcnow
from ..services.permissions import ToolDisabledError, ToolNotFoundError, get_tool_record
from ..services.secrets import GEMINI_SECRET_KEY, TELEGRAM_SECRET_KEY, get_secret
from ..tools.registry import ToolContext, call_tool, validate_tool_arguments
from . import tools as assistant_tools

ACTION_LABELS = {
    "delete_application_record": "حذف رکورد",
    "send_telegram_message": "ارسال پیام تلگرام",
    "prepare_salon_outreach": "آماده‌سازی متن پیگیری سالن",
    "prepare_project_proposal": "آماده‌سازی پروپوزال",
    "generate_outreach_script": "ساخت متن ارتباطی",
    "draft_project_proposal": "پروپوزال پروژه",
    "prepare_delete": "بررسی حذف",
    "create_salon": "افزودن سالن",
    "create_task": "ساخت تسک",
    "create_personal_project": "ساخت پروژه",
    "create_playbook": "ساخت پلی‌بوک",
    "set_tool_policy": "تغییر سیاست ابزار",
    "set_model_preference": "انتخاب مدل",
    "set_default_reminder_window": "تنظیم بازه یادآوری",
    "log_salon_interaction": "ثبت تعامل سالن",
    "update_salon": "ویرایش سالن",
    "update_task": "ویرایش تسک",
    "update_personal_project": "ویرایش پروژه",
    "schedule_task": "زمان‌بندی تسک",
    "add_task_step": "افزودن مرحله تسک",
    "run_task": "اجرای تسک",
}


@dataclass(slots=True)
class ActionOutcome:
    ok: bool
    needs_approval: bool
    action: dict[str, Any]
    function_result: dict[str, Any] | None
    ran: bool


def action_label(action_name: str) -> str:
    return ACTION_LABELS.get(action_name, action_name)


def redact_secrets(db: Session, text: str) -> str:
    """Never persist or return raw secrets inside tool errors."""

    redacted = text
    for key in (GEMINI_SECRET_KEY, TELEGRAM_SECRET_KEY):
        try:
            secret = get_secret(db, key)
        except Exception:
            secret = None
        if secret and len(secret) >= 8:
            redacted = redacted.replace(secret, "••••")
    return redacted


def _function_result(
    action_name: str, provider_call_id: str, payload: dict[str, Any]
) -> dict[str, Any]:
    text = json.dumps(payload, ensure_ascii=False, default=str)
    return {
        "type": "function_result",
        "name": action_name,
        "call_id": provider_call_id,
        "result": [{"type": "text", "text": text}],
    }


def _duplicate_outcome(
    run: AgentActionRun,
) -> ActionOutcome:
    """Replay an already-recorded outcome without re-executing the tool."""

    if run.status == "done":
        action = {
            "name": run.action_name,
            "ok": True,
            "arguments": run.arguments,
            "result": run.result,
            "error": None,
            "idempotent": True,
        }
        return ActionOutcome(
            ok=True,
            needs_approval=False,
            action=action,
            function_result=_function_result(
                run.action_name, run.provider_call_id, run.result or {}
            ),
            ran=False,
        )
    if run.status == "needs_approval":
        action = {
            "name": run.action_name,
            "ok": True,
            "needs_approval": True,
            "arguments": run.arguments,
            "result": None,
            "error": None,
            "idempotent": True,
        }
        return ActionOutcome(
            ok=True,
            needs_approval=True,
            action=action,
            function_result=_function_result(
                run.action_name,
                run.provider_call_id,
                {"status": "needs_approval", "step_id": run.step_id},
            ),
            ran=False,
        )
    error = run.error or "Previous attempt did not complete"
    action = {
        "name": run.action_name,
        "ok": False,
        "arguments": run.arguments,
        "result": None,
        "error": error,
        "idempotent": True,
    }
    return ActionOutcome(
        ok=False,
        needs_approval=False,
        action=action,
        function_result=_function_result(run.action_name, run.provider_call_id, {"error": error}),
        ran=False,
    )


async def execute_action(
    db: Session,
    *,
    conversation_id: int,
    message_id: int | None,
    provider_call_id: str,
    action_name: str,
    arguments: dict[str, Any],
) -> ActionOutcome:
    """Execute one model function call exactly once, respecting policy."""

    existing = db.scalar(
        select(AgentActionRun).where(AgentActionRun.provider_call_id == provider_call_id)
    )
    if existing is not None:
        return _duplicate_outcome(existing)

    try:
        registered, policy = get_tool_record(db, action_name)
    except ToolNotFoundError as exc:
        safe = redact_secrets(db, str(exc))
        action = {
            "name": action_name,
            "ok": False,
            "arguments": arguments,
            "result": None,
            "error": safe,
        }
        return ActionOutcome(
            ok=False,
            needs_approval=False,
            action=action,
            function_result=_function_result(action_name, provider_call_id, {"error": safe}),
            ran=False,
        )
    except ToolDisabledError as exc:
        safe = redact_secrets(db, str(exc))
        action = {
            "name": action_name,
            "ok": False,
            "arguments": arguments,
            "result": None,
            "error": safe,
        }
        return ActionOutcome(
            ok=False,
            needs_approval=False,
            action=action,
            function_result=_function_result(action_name, provider_call_id, {"error": safe}),
            ran=False,
        )

    try:
        validate_tool_arguments(registered, dict(arguments or {}))
    except ValueError as exc:
        safe = redact_secrets(db, str(exc))
        action = {
            "name": action_name,
            "ok": False,
            "arguments": arguments,
            "result": None,
            "error": safe,
        }
        return ActionOutcome(
            ok=False,
            needs_approval=False,
            action=action,
            function_result=_function_result(action_name, provider_call_id, {"error": safe}),
            ran=False,
        )

    run = AgentActionRun(
        conversation_id=conversation_id,
        message_id=message_id,
        provider_call_id=provider_call_id,
        action_name=action_name,
        arguments=dict(arguments or {}),
        status="pending",
    )
    db.add(run)
    db.flush()

    if policy.requires_approval:
        # Pre-register external artifacts so nothing is sent before approval.
        if action_name == "send_telegram_message":
            try:
                assistant_tools.queue_outbound_message(
                    db,
                    provider_call_id=provider_call_id,
                    content=str(arguments.get("content") or ""),
                    owner_type=str(arguments.get("owner_type") or "general"),
                    owner_id=arguments.get("owner_id"),
                    contact_endpoint_id=arguments.get("contact_endpoint_id"),
                )
            except ValueError as exc:
                db.rollback()
                return ActionOutcome(
                    ok=False,
                    needs_approval=False,
                    action={
                        "name": action_name,
                        "ok": False,
                        "arguments": arguments,
                        "result": None,
                        "error": redact_secrets(db, str(exc)),
                    },
                    function_result=_function_result(
                        action_name, provider_call_id, {"error": redact_secrets(db, str(exc))}
                    ),
                    ran=False,
                )

        task = Task(
            title=f"تأیید: {action_label(action_name)}",
            module_name=ASSISTANT_MODULE,
            status="paused",
            description=f"Agent action {action_name} with id {provider_call_id[:40]}",
        )
        db.add(task)
        db.flush()
        step = Step(
            task_id=task.id,
            title=action_label(action_name),
            position=0,
            status="needs_approval",
            tool_name=action_name,
            arguments=dict(arguments or {}),
            requires_approval=True,
        )
        db.add(step)
        db.flush()
        run.step_id = step.id
        run.status = "needs_approval"
        db.commit()
        db.refresh(run)
        action = {
            "name": action_name,
            "ok": True,
            "needs_approval": True,
            "arguments": arguments,
            "result": None,
            "step_id": step.id,
            "error": None,
        }
        return ActionOutcome(
            ok=True,
            needs_approval=True,
            action=action,
            function_result=_function_result(
                action_name,
                provider_call_id,
                {"status": "needs_approval", "step_id": step.id},
            ),
            ran=False,
        )

    run.status = "running"
    run.started_at = utcnow()
    db.commit()
    try:
        result = await call_tool(
            registered,
            ToolContext(db=db, task=None, step=None, call_id=provider_call_id, action_run=run),
            dict(arguments or {}),
        )
        run = db.get(AgentActionRun, run.id)
        run.status = "done"
        run.result = result
        run.error = None
        run.finished_at = utcnow()
        db.commit()
        db.refresh(run)
        action = {
            "name": action_name,
            "ok": True,
            "arguments": arguments,
            "result": result,
            "error": None,
            "id": run.id,
        }
        return ActionOutcome(
            ok=True,
            needs_approval=False,
            action=action,
            function_result=_function_result(action_name, provider_call_id, result or {}),
            ran=True,
        )
    except Exception as exc:
        db.rollback()
        persisted = db.get(AgentActionRun, run.id)
        safe = redact_secrets(db, str(exc) or exc.__class__.__name__)
        if persisted is not None:
            persisted.status = "failed"
            persisted.error = safe[:2000]
            persisted.finished_at = utcnow()
            db.commit()
        action = {
            "name": action_name,
            "ok": False,
            "arguments": arguments,
            "result": None,
            "error": safe,
            "id": persisted.id if persisted else None,
        }
        return ActionOutcome(
            ok=False,
            needs_approval=False,
            action=action,
            function_result=_function_result(action_name, provider_call_id, {"error": safe}),
            ran=False,
        )


ASSISTANT_MODULE = "assistant"
