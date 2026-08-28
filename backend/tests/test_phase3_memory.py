from __future__ import annotations

import pytest
from sqlalchemy import func, select

from backend.app.memory import embedder
from backend.app.memory.chunking import chunk_playbook
from backend.app.memory.embedder import EmbeddingError
from backend.app.memory.store import add_memory, cosine_similarity, search_memory
from backend.app.models import MemoryEntry, Step
from backend.app.tools.registry import ToolContext, register_tool

pytestmark = pytest.mark.asyncio


async def test_playbook_upload_creates_multiple_embedded_memory_rows(client, db):
    content = (
        "Salon outreach cadence: contact warm salon leads every seven days. " * 5
        + "\n\n"
        + "Qualify each salon by location and team size before sending a message. " * 5
        + "\n\n"
        + "Record every reply and schedule the next follow-up clearly. " * 5
    )
    response = await client.post(
        "/api/playbooks",
        json={
            "title": "Salon Growth",
            "content": content,
            "module_name": "salon",
            "chunk_size": 220,
        },
    )
    assert response.status_code == 201, response.text
    assert response.json()["chunk_count"] >= 3

    rows = list(
        db.scalars(
            select(MemoryEntry).where(
                MemoryEntry.source == "playbook",
                MemoryEntry.source_id == str(response.json()["id"]),
            )
        )
    )
    assert len(rows) == response.json()["chunk_count"]
    assert all(row.embedding is not None and len(row.embedding) == 128 for row in rows)


async def test_semantic_search_ranks_related_memory_higher(db):
    # Tests use the deterministic local embedding backend (no paid/network API calls).
    salon = add_memory(
        db,
        content="salon outreach clients hair beauty appointments follow-up",
        source="test",
    )
    cooking = add_memory(
        db,
        content="cooking pasta tomato recipe kitchen boiling dinner",
        source="test",
    )
    ranked = search_memory(db, "salon client outreach follow-up", limit=2)
    assert [item.entry.id for item in ranked] == [salon.id, cooking.id]
    assert ranked[0].score > ranked[1].score


async def test_completed_step_result_is_saved_once_to_memory(client, db):
    task = (await client.post("/api/tasks", json={"title": "Remember this"})).json()
    step = (
        await client.post(
            "/api/steps",
            json={"task_id": task["id"], "title": "Produce result", "position": 0},
        )
    ).json()
    completed = await client.patch(
        f"/api/steps/{step['id']}",
        json={"status": "done", "result": {"proposal": "Accepted"}},
    )
    assert completed.status_code == 200, completed.text
    db.expire_all()
    entries = list(
        db.scalars(
            select(MemoryEntry).where(
                MemoryEntry.source == "task_result",
                MemoryEntry.source_id == str(step["id"]),
            )
        )
    )
    assert len(entries) == 1
    assert "Accepted" in entries[0].content
    assert len(entries[0].embedding) == 128

    # An idempotent repeated update does not duplicate memory.
    assert (
        await client.patch(f"/api/steps/{step['id']}", json={"status": "done"})
    ).status_code == 200
    db.expire_all()
    count = db.scalar(
        select(func.count(MemoryEntry.id)).where(
            MemoryEntry.source == "task_result",
            MemoryEntry.source_id == str(step["id"]),
        )
    )
    assert count == 1


async def test_memory_and_playbook_endpoint_edge_cases(client):
    blank = await client.post("/api/playbooks", json={"title": "x", "content": "   "})
    assert blank.status_code == 422
    assert (await client.get("/api/playbooks/98765")).status_code == 404
    assert (await client.delete("/api/playbooks/98765")).status_code == 404
    assert (await client.delete("/api/memory/98765")).status_code == 404
    assert (await client.get("/api/memory/search", params={"q": ""})).status_code == 422


async def test_embedding_retry_uses_backoff_then_succeeds(monkeypatch):
    monkeypatch.setenv("EMBEDDING_BACKEND", "gemini")
    attempts = []
    delays = []

    def fake_gemini(_text, _task_type):
        attempts.append(1)
        if len(attempts) < 3:
            raise TimeoutError("embedding timeout")
        return [0.25, 0.75]

    monkeypatch.setattr(embedder, "_gemini_embedding", fake_gemini)
    vector = embedder.embed_text("retry me", sleep=delays.append)
    assert vector == [0.25, 0.75]
    assert len(attempts) == 3
    assert delays == [0.25, 0.5]


async def test_embedding_failure_returns_502_and_rolls_back(client, db, monkeypatch):
    def fail_embedding(*_args, **_kwargs):
        raise EmbeddingError("provider unavailable")

    monkeypatch.setattr(embedder, "embed_text", fail_embedding)
    response = await client.post(
        "/api/playbooks",
        json={"title": "Will rollback", "content": "Enough valid content"},
    )
    assert response.status_code == 502
    assert "provider unavailable" in response.json()["detail"]
    assert (await client.get("/api/playbooks")).json() == []
    assert (await client.get("/api/memory")).json() == []


async def test_tool_memory_failure_is_audited_not_uncaught(client, db, monkeypatch):
    @register_tool("phase3_memory_failure", "Memory failure test", requires_approval=False)
    def succeeds_before_memory(_context: ToolContext):
        return {"external": "result"}

    task = (await client.post("/api/tasks", json={"title": "Memory error"})).json()

    def fail_embedding(*_args, **_kwargs):
        raise EmbeddingError("embedding service down")

    monkeypatch.setattr(embedder, "embed_text", fail_embedding)
    response = await client.post(
        "/api/tools/phase3_memory_failure/invoke",
        json={"task_id": task["id"], "arguments": {}},
    )
    assert response.status_code == 502
    assert "embedding service down" in response.text
    db.expire_all()
    step = db.query(Step).filter(Step.task_id == task["id"]).one()
    assert step.status == "failed"
    assert "embedding service down" in step.error


async def test_chunking_and_cosine_logic():
    chunks = chunk_playbook("first short paragraph\n\n" + "word " * 100, max_chars=100)
    assert len(chunks) > 2
    assert all(chunk and len(chunk) <= 100 for chunk in chunks)
    assert cosine_similarity([1.0, 0.0], [1.0, 0.0]) == pytest.approx(1.0)
    assert cosine_similarity([1.0, 0.0], [0.0, 1.0]) == pytest.approx(0.0)
    assert cosine_similarity([], []) == 0.0
