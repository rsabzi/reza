"""Conversational assistant API."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy.orm import Session

from ..agent.ai_client import (
    AIConfigurationError,
    AIProviderError,
    ChatClient,
    get_ai_client,
)
from ..assistant.schemas import (
    ChatRequest,
    ChatResponse,
    ConversationCreate,
    ConversationDetail,
    ConversationRead,
    ConversationSummary,
)
from ..assistant.service import (
    AssistantError,
    NoApiKeyError,
    conversation_detail,
    run_chat_turn,
    summary_for_list,
)
from ..database import get_db
from ..models import AgentActionRun, AgentConversation
from ..services.secrets import gemini_secret_status

router = APIRouter(prefix="/assistant", tags=["assistant"])


def _ensure_gemini_configured(db: Session) -> None:
    try:
        status_info = gemini_secret_status(db)
    except Exception as exc:
        raise HTTPException(status_code=500, detail="Secret store is not readable") from exc
    if not status_info.get("configured"):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=(
                "کلید Gemini هنوز تنظیم نشده است. از صفحه تنظیمات، کلید را وارد و اعتبارسنجی کنید."
            ),
        )


@router.post("/chat", response_model=ChatResponse)
async def chat(
    payload: ChatRequest,
    db: Session = Depends(get_db),
    ai_client: ChatClient = Depends(get_ai_client),
) -> dict[str, Any]:
    _ensure_gemini_configured(db)
    try:
        result = await run_chat_turn(
            db,
            client=ai_client,
            message=payload.message,
            conversation_id=payload.conversation_id,
        )
    except NoApiKeyError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except AssistantError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except AIConfigurationError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except AIProviderError as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"ارتباط با Gemini با خطا مواجه شد؛ بعد از چند لحظه دوباره تلاش کنید. ({exc})",
        ) from exc
    return result


@router.get("/conversations", response_model=list[ConversationSummary])
def list_conversations(db: Session = Depends(get_db)) -> list[dict[str, Any]]:
    return summary_for_list(db)


@router.post("/conversations", response_model=ConversationRead, status_code=status.HTTP_201_CREATED)
def create_conversation(
    payload: ConversationCreate, db: Session = Depends(get_db)
) -> AgentConversation:
    conversation = AgentConversation(title=payload.title or "گفتگوی جدید", status="active")
    db.add(conversation)
    db.commit()
    db.refresh(conversation)
    return conversation


@router.get("/conversations/{conversation_id}", response_model=ConversationDetail)
def get_conversation(conversation_id: int, db: Session = Depends(get_db)) -> dict[str, Any]:
    conversation = conversation_detail(db, conversation_id)
    if conversation is None:
        raise HTTPException(status_code=404, detail="Conversation not found")
    messages = [
        {
            "id": item.id,
            "role": item.role,
            "content": item.content,
            "actions": item.actions or [],
            "created_at": item.created_at,
        }
        for item in conversation.messages
    ]
    runs = [
        {
            "id": item.id,
            "conversation_id": item.conversation_id,
            "message_id": item.message_id,
            "provider_call_id": item.provider_call_id,
            "action_name": item.action_name,
            "arguments": item.arguments,
            "status": item.status,
            "result": item.result,
            "error": item.error,
            "started_at": item.started_at,
            "finished_at": item.finished_at,
        }
        for item in conversation.action_runs
    ]
    return {
        "id": conversation.id,
        "title": conversation.title,
        "status": conversation.status,
        "messages": messages,
        "action_runs": runs,
        "created_at": conversation.created_at,
        "updated_at": conversation.updated_at,
    }


@router.delete("/conversations/{conversation_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_conversation(conversation_id: int, db: Session = Depends(get_db)) -> Response:
    conversation = db.get(AgentConversation, conversation_id)
    if conversation is None:
        raise HTTPException(status_code=404, detail="Conversation not found")
    db.delete(conversation)
    db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post(
    "/conversations/{conversation_id}/archive",
    response_model=ConversationRead,
)
def archive_conversation(conversation_id: int, db: Session = Depends(get_db)) -> AgentConversation:
    conversation = db.get(AgentConversation, conversation_id)
    if conversation is None:
        raise HTTPException(status_code=404, detail="Conversation not found")
    conversation.status = "archived"
    db.commit()
    db.refresh(conversation)
    return conversation


@router.get("/actions", response_model=list[dict[str, Any]])
def list_action_runs(
    conversation_id: int | None = None, db: Session = Depends(get_db)
) -> list[dict[str, Any]]:
    from sqlalchemy import select

    statement = select(AgentActionRun).order_by(AgentActionRun.created_at.desc()).limit(200)
    if conversation_id is not None:
        statement = statement.where(AgentActionRun.conversation_id == conversation_id)
    return [
        {
            "id": item.id,
            "conversation_id": item.conversation_id,
            "message_id": item.message_id,
            "provider_call_id": item.provider_call_id,
            "action_name": item.action_name,
            "arguments": item.arguments,
            "status": item.status,
            "result": item.result,
            "error": item.error,
            "started_at": item.started_at,
            "finished_at": item.finished_at,
        }
        for item in db.scalars(statement)
    ]
