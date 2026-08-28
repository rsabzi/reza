"""Playbook ingestion and memory browsing/search API."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from pydantic import BaseModel, ConfigDict, Field, field_validator
from sqlalchemy import delete, func, select
from sqlalchemy.orm import Session

from ..database import get_db
from ..memory.chunking import chunk_playbook
from ..memory.embedder import EmbeddingError
from ..memory.store import add_memory, search_memory
from ..models import MemoryEntry, Playbook

router = APIRouter(tags=["memory"])


class PlaybookCreate(BaseModel):
    title: str = Field(min_length=1, max_length=255)
    content: str = Field(min_length=1)
    module_name: str | None = Field(default=None, max_length=64)
    chunk_size: int = Field(default=800, ge=100, le=5000)

    @field_validator("title", "content")
    @classmethod
    def not_blank(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("must not be blank")
        return value.strip()


class PlaybookRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    title: str
    content: str
    module_name: str | None
    created_at: datetime
    updated_at: datetime
    chunk_count: int = 0


class MemoryRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    content: str
    source: str
    source_id: str | None
    module_name: str | None
    embedding: list[float]
    entry_metadata: dict[str, Any]
    created_at: datetime


class MemorySearchRead(MemoryRead):
    score: float


@router.post("/playbooks", response_model=PlaybookRead, status_code=status.HTTP_201_CREATED)
def upload_playbook(payload: PlaybookCreate, db: Session = Depends(get_db)) -> dict[str, Any]:
    playbook = Playbook(
        title=payload.title, content=payload.content, module_name=payload.module_name
    )
    db.add(playbook)
    db.flush()
    chunks = chunk_playbook(payload.content, max_chars=payload.chunk_size)
    try:
        for index, chunk in enumerate(chunks):
            add_memory(
                db,
                content=chunk,
                source="playbook",
                source_id=str(playbook.id),
                module_name=payload.module_name,
                metadata={
                    "playbook_id": playbook.id,
                    "chunk_index": index,
                    "title": playbook.title,
                },
                commit=False,
            )
        db.commit()
    except (EmbeddingError, ValueError) as exc:
        db.rollback()
        raise HTTPException(status_code=502, detail=f"Playbook embedding failed: {exc}") from exc
    db.refresh(playbook)
    return {
        **PlaybookRead.model_validate(playbook).model_dump(),
        "chunk_count": len(chunks),
    }


@router.get("/playbooks", response_model=list[PlaybookRead])
def list_playbooks(db: Session = Depends(get_db)) -> list[dict[str, Any]]:
    books = list(db.scalars(select(Playbook).order_by(Playbook.created_at.desc())))
    result = []
    for book in books:
        count = (
            db.scalar(
                select(func.count(MemoryEntry.id)).where(
                    MemoryEntry.source == "playbook",
                    MemoryEntry.source_id == str(book.id),
                )
            )
            or 0
        )
        result.append({**PlaybookRead.model_validate(book).model_dump(), "chunk_count": count})
    return result


@router.get("/playbooks/{playbook_id}", response_model=PlaybookRead)
def get_playbook(playbook_id: int, db: Session = Depends(get_db)) -> dict[str, Any]:
    book = db.get(Playbook, playbook_id)
    if book is None:
        raise HTTPException(status_code=404, detail="Playbook not found")
    count = (
        db.scalar(
            select(func.count(MemoryEntry.id)).where(
                MemoryEntry.source == "playbook", MemoryEntry.source_id == str(book.id)
            )
        )
        or 0
    )
    return {**PlaybookRead.model_validate(book).model_dump(), "chunk_count": count}


@router.delete("/playbooks/{playbook_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_playbook(playbook_id: int, db: Session = Depends(get_db)) -> Response:
    book = db.get(Playbook, playbook_id)
    if book is None:
        raise HTTPException(status_code=404, detail="Playbook not found")
    db.execute(
        delete(MemoryEntry).where(
            MemoryEntry.source == "playbook", MemoryEntry.source_id == str(book.id)
        )
    )
    db.delete(book)
    db.commit()
    return Response(status_code=204)


@router.get("/memory", response_model=list[MemoryRead])
def list_memory(
    source: str | None = None,
    module_name: str | None = None,
    limit: int = Query(default=50, ge=1, le=200),
    db: Session = Depends(get_db),
) -> list[MemoryEntry]:
    statement = select(MemoryEntry).order_by(MemoryEntry.created_at.desc()).limit(limit)
    if source:
        statement = statement.where(MemoryEntry.source == source)
    if module_name:
        statement = statement.where(MemoryEntry.module_name == module_name)
    return list(db.scalars(statement))


@router.get("/memory/search", response_model=list[MemorySearchRead])
def search_memory_endpoint(
    q: str = Query(min_length=1),
    limit: int = Query(default=5, ge=1, le=100),
    source: str | None = None,
    module_name: str | None = None,
    db: Session = Depends(get_db),
) -> list[dict[str, Any]]:
    try:
        results = search_memory(db, q, limit=limit, source=source, module_name=module_name)
    except (EmbeddingError, ValueError) as exc:
        raise HTTPException(status_code=502, detail=f"Memory search failed: {exc}") from exc
    return [
        {**MemoryRead.model_validate(item.entry).model_dump(), "score": item.score}
        for item in results
    ]


@router.delete("/memory/{entry_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_memory(entry_id: int, db: Session = Depends(get_db)) -> Response:
    entry = db.get(MemoryEntry, entry_id)
    if entry is None:
        raise HTTPException(status_code=404, detail="Memory entry not found")
    db.delete(entry)
    db.commit()
    return Response(status_code=204)
