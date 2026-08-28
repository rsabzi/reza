# Phase 4 Report — Planner & Executor

## Built

- Async Gemini `gemini-2.5-flash` client with dependency injection for deterministic tests.
- Memory-aware planner, strict JSON-plan parser, exponential retry, and one `AILog` row per attempt (including mocked calls and failures).
- Sequential executor with explicit pause states for approval and user input.
- Persisted `approved_at` audit field; approval resumes the approved step and all remaining steps.
- Rejection flow and terminal task-state updates.
- Plan, execute, approve, reject, and AI-log APIs with clear 404/409/502 behavior.

## Acceptance criteria

- [x] Mocked Gemini response creates the exact expected Steps.
- [x] Executor stops at the first approval and leaves every later step pending.
- [x] Approve endpoint resumes current and remaining steps end-to-end.
- [x] Timeout then success retries with asserted 0.25-second backoff (sleep mocked).
- [x] Every AI attempt is persisted in `AILog`; failure and success rows are asserted.
- [x] Automated suite has zero failures.
- [ ] **External-only check blocked:** a real Gemini end-to-end call could not be run because this environment has neither `GEMINI_API_KEY` nor `GOOGLE_API_KEY`. No output was fabricated. The real client and failure path were manually exercised; configure the key in the process environment and rerun the command below to close this item.

## Automated test run

```bash
EMBEDDING_BACKEND=local .venv/bin/python -m pytest -v \
  backend/tests/test_phase1_core.py backend/tests/test_phase2_tools.py \
  backend/tests/test_phase3_memory.py backend/tests/test_phase4_agent.py
```

```text
collected 23 items
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
backend/tests/test_phase4_agent.py::test_decompose_task_with_mocked_ai_creates_expected_steps PASSED
backend/tests/test_phase4_agent.py::test_executor_stops_at_approval_and_leaves_later_steps_pending PASSED
backend/tests/test_phase4_agent.py::test_approve_endpoint_resumes_current_and_remaining_steps PASSED
backend/tests/test_phase4_agent.py::test_ai_timeout_retries_with_backoff_and_logs_every_call PASSED
backend/tests/test_phase4_agent.py::test_plan_endpoint_and_failure_edges PASSED
backend/tests/test_phase4_agent.py::test_reject_and_invalid_approval_states PASSED
backend/tests/test_phase4_agent.py::test_plan_parser_rejects_malformed_payloads PASSED
============================== 23 passed in 0.69s ==============================
```

## Manual API check

Actual missing-key graceful-failure and audit result:

```text
$ curl -X POST /api/tasks/1/plan
{"detail":"Planning failed after 3 attempts: GEMINI_API_KEY is not configured; add it to the environment before planning"} HTTP_502

$ curl '/api/ai-logs?task_id=1' | compact
[{"attempt":3,"model":"gemini-2.5-flash","error":"GEMINI_API_KEY is not configured..."},
 {"attempt":2,"model":"gemini-2.5-flash","error":"GEMINI_API_KEY is not configured..."},
 {"attempt":1,"model":"gemini-2.5-flash","error":"GEMINI_API_KEY is not configured..."}]
```

Actual approval/resume flow:

```text
$ curl -X POST /api/tasks/2/execute | compact
{"task_status":"paused","steps":[{"id":1,"status":"needs_approval"},{"id":2,"status":"pending"}]}

$ curl -X POST /api/steps/1/approve | compact
{"task_status":"done","steps":[
 {"id":1,"status":"done","result":{"value":"approved value"}},
 {"id":2,"status":"done","result":{"value":"later"}}]}

$ curl '/api/steps?step_status=needs_approval'
[]

$ curl -X POST /api/steps/1/reject
{"detail":"Step is not waiting for approval"} HTTP_409
```

## Real Gemini verification command

After setting a key in the shell (do not commit it), start the API and run:

```bash
TASK_ID=$(curl -s -X POST http://127.0.0.1:8000/api/tasks \
  -H 'content-type: application/json' \
  -d '{"title":"برای معرفی خدمات به یک سالن برنامه سه مرحله‌ای بساز"}' \
  | python -c 'import json,sys; print(json.load(sys.stdin)["id"])')
curl -s -X POST "http://127.0.0.1:8000/api/tasks/$TASK_ID/plan"
curl -s -X POST "http://127.0.0.1:8000/api/tasks/$TASK_ID/execute"
```

## Changes to earlier-phase code

- `Step` gained `approved_at`.
- Step listing gained a status filter.
- The existing registry/memory completion path is reused by Executor; core module boundaries remain intact.
- All Phase 1–3 tests were rerun successfully.

## Later regression hardening

Final review added an API-level exhausted-retry test: three simulated Gemini timeouts produce a controlled HTTP 502 response and exactly three persisted error logs. Together with the direct retry-then-success test, this verifies both recovery and terminal failure paths. The final Backend suite is **42 passed**.

## Known limitations

The real Gemini acceptance check remains pending solely because no API credential is available in the execution environment. This report intentionally does **not** claim that external acceptance item as passed.
