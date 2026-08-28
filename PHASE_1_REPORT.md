# Phase 1 Report — Core Models

## Built

- FastAPI application with SQLite/SQLAlchemy 2 session management and enforced SQLite foreign keys.
- Core models: `Task`, `Step`, `Tool`, `Permission`, `AILog`, and `Module`.
- Pydantic request/response validation.
- Full Task and Step CRUD APIs, list/filter APIs, clear 404/409/422 errors, and Task → Step cascade deletion.
- Async API test fixture using `httpx.AsyncClient` + `ASGITransport`.

## Acceptance criteria

- [x] Task create/read/update/delete tested.
- [x] Step create/read/update/delete and parent link tested.
- [x] Task deletion cascades to Step rows; explicitly queried from the DB after deletion.
- [x] Missing/blank required input returns 422 with field-level detail.
- [x] Missing records return 404.
- [x] Duplicate `(task_id, position)` DB constraint returns 409 and is tested.

## Automated test run

Command:

```bash
.venv/bin/python -m pytest -v backend/tests/test_phase1_core.py
```

Actual output:

```text
============================= test session starts ==============================
platform linux -- Python 3.11.2, pytest-8.4.1, pluggy-1.6.0
rootdir: /home/user/reza
configfile: pytest.ini
plugins: anyio-4.14.2, asyncio-1.1.0
asyncio: mode=Mode.AUTO
collected 5 items

backend/tests/test_phase1_core.py::test_task_full_crud PASSED            [ 20%]
backend/tests/test_phase1_core.py::test_step_full_crud_and_parent_link PASSED [ 40%]
backend/tests/test_phase1_core.py::test_deleting_task_cascades_to_steps PASSED [ 60%]
backend/tests/test_phase1_core.py::test_validation_and_duplicate_position_errors PASSED [ 80%]
backend/tests/test_phase1_core.py::test_missing_records_return_404 PASSED [100%]

============================== 5 passed in 0.16s ===============================
```

## Manual API check

Server command:

```bash
.venv/bin/uvicorn backend.app.main:app --host 0.0.0.0 --port 8000
```

Representative actual requests/responses (all CRUD/list endpoints were called):

```text
$ curl -s http://127.0.0.1:8000/api/health
{"status":"ok","service":"Agent Core"}

$ curl -s -X POST http://127.0.0.1:8000/api/tasks ...
{"id":1,"title":"Manual phase 1 task","description":"curl verification","status":"pending",...}

$ curl -s http://127.0.0.1:8000/api/tasks/1
{"id":1,"title":"Manual phase 1 task",...,"steps":[]}

$ curl -s -X PATCH http://127.0.0.1:8000/api/tasks/1 -d '{"status":"running"}'
{"id":1,...,"status":"running",...}

$ curl -s -X POST http://127.0.0.1:8000/api/steps ...
{"id":1,"task_id":1,"title":"Manual step","position":0,"status":"pending",...}

$ curl -s 'http://127.0.0.1:8000/api/steps?task_id=1'
[{"id":1,"task_id":1,"title":"Manual step",...}]

$ curl -s -X PATCH http://127.0.0.1:8000/api/steps/1 -d '{"status":"done","result":{"verified":true}}'
{"id":1,...,"status":"done","result":{"verified":true},...}

$ curl -X DELETE http://127.0.0.1:8000/api/steps/1
HTTP_204
$ curl -X DELETE http://127.0.0.1:8000/api/tasks/1
HTTP_204
```

## Known limitations

None for the Phase 1 scope. Schema migration tooling is intentionally deferred; this first local single-user version creates missing tables at startup.
