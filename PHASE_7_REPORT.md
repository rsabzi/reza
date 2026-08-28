# Phase 7 Report — Personal/Freelance Module

## Built

- Isolated `modules/personal/` package with model, schemas, service, routes, and tools.
- Full PersonalProject CRUD with an explicit transition graph and HTTP 409 for illegal transitions.
- Non-negative budget enforced both by Pydantic and a database CHECK constraint.
- Three-day reminder window (`N = 3`), configurable from 0–365 days at the endpoint.
- Reminder excludes overdue, out-of-range, undated, and terminal projects.
- Guarded `draft_project_proposal` and immediate `daily_personal_reminder` tools.

## Acceptance criteria

- [x] Create/read/list/update/delete Project tested.
- [x] Legal `lead → active → submitted → won` transitions tested; terminal reversal rejected.
- [x] `draft_project_proposal` registered with approval required.
- [x] Reminder includes day 0 and day 3, excludes day 4, overdue, complete, and undated fixtures.
- [x] API validation/error and DB constraint cases tested.
- [x] Entire Backend regression suite has zero failures.

## Automated test run

```bash
EMBEDDING_BACKEND=local .venv/bin/python -m pytest -v
```

```text
collected 38 items
[Phase 1–6: 33 tests] PASSED
backend/tests/test_phase7_personal.py::test_personal_project_full_crud_and_status_transitions PASSED
backend/tests/test_phase7_personal.py::test_draft_project_proposal_is_registered_with_approval PASSED
backend/tests/test_phase7_personal.py::test_daily_reminder_includes_only_next_three_days PASSED
backend/tests/test_phase7_personal.py::test_reminder_endpoint_and_project_validation_edges PASSED
backend/tests/test_phase7_personal.py::test_budget_database_constraint PASSED
============================== 38 passed in 1.07s ==============================
```

## Core isolation regression

```text
$ grep -RniE 'salon|سالن|personal|freelance|project_proposal' \
    backend/app/agent backend/app/tools/registry.py backend/app/memory
(no matches)
```

## Manual API check

Actual excerpts:

```text
$ curl -X POST /api/personal/projects -d ...
{"id":1,"title":"طراحی لندینگ پیج","client_name":"کارفرمای نمونه",
 "status":"lead","due_date":"2026-08-29","budget":"1500.00",
 "next_action":"تهیه وایرفریم",...}

$ curl /api/personal/projects
[{"id":1,"title":"طراحی لندینگ پیج",...,"status":"lead"}]

$ curl /api/personal/projects/1
{"id":1,"title":"طراحی لندینگ پیج",...,"status":"lead"}

$ curl -X PATCH /api/personal/projects/1 -d '{"status":"active"}'
{"id":1,...,"status":"active",...}

$ curl '/api/personal/reminders?today=2026-08-27&within_days=3'
[{"project":{"id":1,"title":"طراحی لندینگ پیج",...,"due_date":"2026-08-29"},
  "days_until_due":2}]
# پروژه عمداً خارج از بازه در پاسخ دیده نمی‌شود.

$ curl /api/tools | select draft_project_proposal
{"name":"draft_project_proposal","requires_approval":true,"enabled":true,...}

$ curl -X POST /api/tools/draft_project_proposal/invoke -d ...
{"status":"needs_approval","tool_name":"draft_project_proposal","result":null,...}

$ curl -X PATCH /api/personal/projects/1 -d '{"status":"won"}'
{"detail":"Cannot transition project from 'active' to 'won'"} HTTP_409

$ curl -X DELETE /api/personal/projects/1
HTTP_204
```

## Changes to earlier-phase code

Only application composition in `main.py` was extended to import/register/mount this module. Core folders remain module-agnostic, confirmed by grep. All earlier tests were rerun.

## Known limitations

This phase models freelance work at Project granularity, matching the requested `PersonalProjects` schema. Generic Agent Core Tasks remain available for smaller day-to-day actions and reminders.
