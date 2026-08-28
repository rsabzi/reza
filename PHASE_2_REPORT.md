# Phase 2 Report — Tool Registry & Permission Layer

## Built

- Framework-independent decorator registry in `backend/app/tools/registry.py`.
- Persisted per-tool approval/enabled policy, while descriptions remain synchronized from code.
- Guarded invocation service that always creates an auditable Step.
- Approval-required tools pause at `needs_approval` without calling the function.
- Immediate sync/async tools execute, store their result, and finish at `done`.
- Tool discovery, policy update, and invocation endpoints.
- Clear 403/404/422/502 handling for disabled, unknown, invalid-policy, and failed tools.

## Acceptance criteria

- [x] Registered tool appears in `GET /api/tools`.
- [x] Approval-required invocation creates `needs_approval`; test proves side-effect list remains empty.
- [x] Unrestricted async tool executes and stores its result.
- [x] PATCH policy change affects the very next invocation.
- [x] Tool-name unique DB constraint explicitly tested.
- [x] Phase 1 regression tests still pass.

## Automated test run

```bash
.venv/bin/python -m pytest -v backend/tests/test_phase1_core.py backend/tests/test_phase2_tools.py
```

```text
collected 11 items
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
============================== 11 passed in 0.32s ==============================
```

## Manual API check

Actual requests/responses:

```text
$ curl -s http://127.0.0.1:8000/api/tools
[{"id":1,"name":"echo","description":"Return the supplied value.","requires_approval":false,"enabled":true}]

$ curl -s -X POST .../api/tools/echo/invoke -d '{"task_id":1,"arguments":{"value":"سلام"}}'
{"id":1,"task_id":1,"status":"done","tool_name":"echo","result":{"value":"سلام"},...}

$ curl -s -X PATCH .../api/tools/echo -d '{"requires_approval":true}'
{"id":1,"name":"echo",...,"requires_approval":true,"enabled":true}

$ curl -s -X POST .../api/tools/echo/invoke -d '{"task_id":2,"arguments":{"value":"not run yet"}}'
{"id":2,"task_id":2,"status":"needs_approval","result":null,"requires_approval":true,...}

$ curl -s -X POST .../api/tools/missing/invoke ...
{"detail":"Tool 'missing' is not registered"} HTTP_404
```

The `echo` policy was restored to its default after this manual test.

## Changes to earlier-phase code

- `main.py` now imports the built-in tool module and mounts the tool router.
- No Phase 1 behavior was changed; all five Phase 1 tests were rerun.

## Known limitations

Approval execution/resumption is intentionally implemented in Phase 4 together with the Executor; Phase 2 only guarantees safe pausing.
