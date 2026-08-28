# Phase 3 Report — Long-Term Memory

## Built

- `MemoryEntry` and `Playbook` persistence models.
- Gemini `text-embedding-004` adapter with retries and clear `EmbeddingError` failures.
- Deterministic 128-dimensional feature-hashing fallback for offline/local use; `auto` selects Gemini whenever a Gemini key exists.
- Memory insertion, idempotent completed-Step capture, cosine similarity, filtering, and top-k search.
- Paragraph/word-safe playbook chunking with configurable bounds.
- Playbook upload/list/read/delete and memory list/search/delete APIs.
- Atomic playbook ingestion: any embedding error rolls back both the Playbook and all chunks.

## Acceptance criteria

- [x] Upload creates several MemoryEntry rows with non-empty 128-value embeddings (offline test backend).
- [x] A salon query ranks a salon chunk over a cooking chunk.
- [x] Completed Step results are automatically saved with `source="task_result"` and are idempotent.
- [x] Chunking and cosine edge cases are unit tested.
- [x] Blank/missing resources and external embedding failures have explicit HTTP errors.
- [x] Phase 1–2 regression suite passes.

## Embedding test policy

Automated tests explicitly run with `EMBEDDING_BACKEND=local`. This is deterministic, has no API cost, and exercises real vector generation/ranking rather than hard-coded search output. In normal `auto` mode, setting `GEMINI_API_KEY` switches to the specified Gemini `text-embedding-004` model. `EMBEDDING_BACKEND=gemini` can force it and fails clearly if no key is configured.

## Automated test run

```bash
EMBEDDING_BACKEND=local .venv/bin/python -m pytest -v \
  backend/tests/test_phase1_core.py backend/tests/test_phase2_tools.py \
  backend/tests/test_phase3_memory.py
```

```text
collected 16 items
backend/tests/test_phase1_core.py::test_task_full_crud PASSED
backend/tests/test_phase1_core.py::test_step_full_crud_and_parent_link PASSED
backend/tests/test_phase1_core.py::test_deleting_task_cascades_to_steps PASSED
backend/tests/test_phase1_core.py::test_validation_and_duplicate_position_errors PASSED
backend/tests/test_phase1_core.py::test_missing_records_return_404 PASSED
backend/tests/test_phase2_tools.py::test_registered_tool_appears_in_tools_endpoint PASSED
backend/tests/test_phase2_tools.py::test_approval_tool_creates_paused_step_without_side_effect PASSED
backend/tests/test_phase2_tools.py::test_unrestricted_tool_executes_and_finishes_step PASSED
backend/tests/test_phase2_tools.py::test_toggling_approval_changes_next_invocation PASSED
backend/tests/test_phase2_tools.py::test_tool_endpoint_failures_are_clear PASSED
backend/tests/test_phase2_tools.py::test_tool_name_database_constraint PASSED
backend/tests/test_phase3_memory.py::test_playbook_upload_creates_multiple_embedded_memory_rows PASSED
backend/tests/test_phase3_memory.py::test_semantic_search_ranks_related_memory_higher PASSED
backend/tests/test_phase3_memory.py::test_completed_step_result_is_saved_once_to_memory PASSED
backend/tests/test_phase3_memory.py::test_memory_and_playbook_endpoint_edge_cases PASSED
backend/tests/test_phase3_memory.py::test_chunking_and_cosine_logic PASSED
============================== 16 passed in 0.44s ==============================
```

## Manual API check

Server was restarted with `EMBEDDING_BACKEND=local`; actual compacted responses:

```text
$ curl -s -X POST http://127.0.0.1:8000/api/playbooks -d ...
{"id":1,"title":"Manual salon playbook",...,"module_name":"salon","chunk_count":3}

$ curl -s http://127.0.0.1:8000/api/playbooks
[{"id":1,"title":"Manual salon playbook",...,"chunk_count":3}]

$ curl -s http://127.0.0.1:8000/api/playbooks/1
{"id":1,"title":"Manual salon playbook",...,"chunk_count":3}

$ curl -s '/api/memory?source=playbook' | compact
[{"id":3,"source":"playbook","content":"qualify each beauty salon ...","embedding_length":128},
 {"id":2,"source":"playbook","content":"cooking pasta tomato ...","embedding_length":128},
 {"id":1,"source":"playbook","content":"salon outreach clients ...","embedding_length":128}]

$ curl -s '/api/memory/search?q=salon%20outreach%20clients&limit=2' | compact
[{"id":1,"content":"salon outreach clients ...","score":0.5222},
 {"id":3,"content":"qualify each beauty salon ...","score":0.1491}]

$ curl -X DELETE /api/memory/3
HTTP_204
$ curl -X DELETE /api/playbooks/1
HTTP_204
```

## Changes to earlier-phase code

- Step PATCH now detects the transition to `done` and atomically saves its non-null result to memory.
- Immediate tool completion now uses the same memory capture function.
- All Phase 1 and Phase 2 tests were rerun successfully.

## Later regression hardening

During final review, three additional tests were added and the full suite rerun: embedding retry/backoff, atomic Playbook rollback on provider failure, and HTTP 502 plus failed-Step audit when post-tool memory embedding fails. The final Backend result is **42 passed**; no uncaught provider exception remains.

## Current provider update (2026-08-28)

Following the current Google embedding documentation, the deprecated original `text-embedding-004` runtime was replaced by `gemini-embedding-001`. Output dimensionality is explicitly fixed at 128 so previously created local vectors and new Gemini vectors remain structurally compatible. The Google Gen AI SDK is now `2.20.0`.

## Known limitations

Local hashing captures lexical similarity, not the full semantic quality of Gemini. It is an intentional offline fallback and test backend; production semantic quality requires a configured Gemini key.
