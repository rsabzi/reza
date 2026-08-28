# Phase 5 Report — Scheduling & Daily Reminders

## Built

- APScheduler background scheduler started/stopped with FastAPI lifespan.
- Coalesced 30-second poller for due daily recurrence templates.
- Timezone-aware scheduling via `AGENT_TIMEZONE` (IANA name; UTC by default).
- Deterministic due-task processor with injectable clock.
- Recurring Task materialization copies the Task and its planned Steps into a one-off instance.
- Same-day duplicate prevention through `last_scheduled_at`.
- Run-now, run-due, and scheduler-status APIs.

## Acceptance criteria

- [x] Injected clock before due time creates nothing; advancing it to due time creates a Task.
- [x] Same-day second poll creates nothing; next-day clock creates exactly one new instance.
- [x] Manual run-now and scheduled trigger have matching semantic fields.
- [x] Cloned Steps reset to `pending` and retain tool arguments.
- [x] Invalid/missing templates return clear 409/404 errors.
- [x] Full Phase 1–5 automated regression suite has zero failures.

## Automated test run

```bash
EMBEDDING_BACKEND=local .venv/bin/python -m pytest -v \
  backend/tests/test_phase1_core.py backend/tests/test_phase2_tools.py \
  backend/tests/test_phase3_memory.py backend/tests/test_phase4_agent.py \
  backend/tests/test_phase5_scheduler.py
```

```text
collected 27 items
[all Phase 1–4 tests] PASSED
backend/tests/test_phase5_scheduler.py::test_daily_rule_creates_instance_when_clock_advances PASSED
backend/tests/test_phase5_scheduler.py::test_run_now_api_matches_scheduled_materialization PASSED
backend/tests/test_phase5_scheduler.py::test_scheduler_endpoint_errors_and_status PASSED
backend/tests/test_phase5_scheduler.py::test_materializer_rejects_invalid_template PASSED
============================== 27 passed in 0.69s ==============================
```

## Manual API check

Actual requests/responses:

```text
$ curl -s http://127.0.0.1:8000/api/scheduler/status
{"running":true,"poll_interval":"30 seconds"}

$ curl -s -X POST /api/tasks/3/run-now | compact
{"id":4,"parent_task_id":3,"title":"Manual daily task","recurrence_rule":null,
 "steps":[{"title":"Daily echo","status":"pending"}]}

$ curl -s -X POST /api/scheduler/run-due -d '{"now":"2026-08-28T09:00:00Z"}'
[{"id":5,"parent_task_id":3,"title":"Manual daily task","recurrence_rule":null}]

$ curl -s -X POST /api/tasks/9999/run-now
{"detail":"Task not found"} HTTP_404
```

## Changes to earlier-phase code

- FastAPI lifespan now starts and cleanly stops APScheduler.
- Existing Task recurrence fields are now actively used; no old API semantics changed.
- Phase 1–4 tests were rerun.

## Known limitations

- Daily schedule interpretation uses one installation-wide timezone (`AGENT_TIMEZONE`), appropriate for the specified single user. Per-task timezones are not in scope.
- The Phase 4 external Gemini check remains separately pending as documented in `PHASE_4_REPORT.md`; scheduler acceptance itself is complete.
