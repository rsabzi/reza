"""Persistence and cosine search for long-term memory."""

from __future__ import annotations

import json
import math
from dataclasses import dataclass
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from ..models import MemoryEntry, Playbook, Step
from . import embedder


@dataclass(frozen=True, slots=True)
class MemorySearchResult:
    entry: MemoryEntry
    score: float


def cosine_similarity(left: list[float], right: list[float]) -> float:
    if not left or not right or len(left) != len(right):
        return 0.0
    left_norm = math.sqrt(sum(value * value for value in left))
    right_norm = math.sqrt(sum(value * value for value in right))
    if left_norm == 0 or right_norm == 0:
        return 0.0
    return sum(a * b for a, b in zip(left, right, strict=True)) / (left_norm * right_norm)


def add_memory(
    db: Session,
    *,
    content: str,
    source: str,
    source_id: str | None = None,
    module_name: str | None = None,
    metadata: dict[str, Any] | None = None,
    embedding: list[float] | None = None,
    commit: bool = True,
) -> MemoryEntry:
    normalized = content.strip()
    if not normalized:
        raise ValueError("Memory content must not be blank")
    vector = embedding or embedder.embed_text(normalized, task_type="RETRIEVAL_DOCUMENT")
    if not vector:
        raise ValueError("Memory embedding must not be empty")
    entry = MemoryEntry(
        content=normalized,
        source=source,
        source_id=source_id,
        module_name=module_name,
        embedding=vector,
        entry_metadata=metadata or {},
    )
    db.add(entry)
    if commit:
        db.commit()
        db.refresh(entry)
    else:
        db.flush()
    return entry


def search_memory(
    db: Session,
    query: str,
    *,
    limit: int = 5,
    source: str | None = None,
    module_name: str | None = None,
) -> list[MemorySearchResult]:
    if limit < 1 or limit > 100:
        raise ValueError("limit must be between 1 and 100")
    query_vector = embedder.embed_text(query, task_type="RETRIEVAL_QUERY")
    statement = select(MemoryEntry)
    if source:
        statement = statement.where(MemoryEntry.source == source)
    if module_name:
        statement = statement.where(MemoryEntry.module_name == module_name)
    entries = list(db.scalars(statement))
    ranked = [
        MemorySearchResult(entry=entry, score=cosine_similarity(query_vector, entry.embedding))
        for entry in entries
    ]
    ranked.sort(key=lambda item: (item.score, item.entry.id), reverse=True)
    return ranked[:limit]


def create_playbook_with_chunks(
    db: Session,
    *,
    title: str,
    content: str,
    module_name: str | None = None,
    chunk_size: int = 800,
) -> Playbook:
    """Persist a playbook and its embedded chunks in one transaction."""

    from .chunking import chunk_playbook

    playbook = Playbook(title=title, content=content, module_name=module_name)
    db.add(playbook)
    db.flush()
    chunks = chunk_playbook(content, max_chars=chunk_size)
    for index, chunk in enumerate(chunks):
        add_memory(
            db,
            content=chunk,
            source="playbook",
            source_id=str(playbook.id),
            module_name=module_name,
            metadata={
                "playbook_id": playbook.id,
                "chunk_index": index,
                "title": playbook.title,
            },
            commit=False,
        )
    db.commit()
    db.refresh(playbook)
    return playbook


def save_completed_step(db: Session, step: Step, *, commit: bool = True) -> MemoryEntry | None:
    """Idempotently save a completed step's result as durable memory."""

    if step.status != "done" or step.result is None:
        return None
    existing = db.scalar(
        select(MemoryEntry).where(
            MemoryEntry.source == "task_result", MemoryEntry.source_id == str(step.id)
        )
    )
    if existing:
        return existing
    if isinstance(step.result, str):
        result_text = step.result
    else:
        result_text = json.dumps(step.result, ensure_ascii=False, sort_keys=True)
    return add_memory(
        db,
        content=f"{step.title}: {result_text}",
        source="task_result",
        source_id=str(step.id),
        module_name=step.task.module_name if step.task else None,
        metadata={"task_id": step.task_id, "step_id": step.id},
        commit=commit,
    )
