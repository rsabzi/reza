# Phase 6 Report — Salon Marketing Module

## Built

- Isolated `modules/salon/` package with its own models, schemas, routes, services, and tools.
- Salon CRUD and resilient bulk import (partial success is HTTP 207 with indexed validation errors).
- Interaction logging, atomically coupled to a `salon_interaction` long-term memory entry.
- Daily plan driven by latest salon Playbook cadence; supports English and Persian/Arabic digits.
- Salon status exclusions (`inactive`, `do_not_contact`, `customer`).
- Registered tools: guarded `generate_outreach_script`, immediate `log_salon_interaction`, and `daily_salon_plan`.

## Acceptance criteria

- [x] Bulk sample creates every valid row and reports the missing-phone row at its original index.
- [x] `generate_outreach_script` is registered with `requires_approval=true`.
- [x] Interaction row and corresponding embedded MemoryEntry are both asserted.
- [x] Explicit key test: Salon X contacted 3 days ago is excluded under a 7-day Playbook rule; 8-day-old and untouched leads remain.
- [x] Phone uniqueness constraint and endpoint errors are tested.
- [x] Core isolation grep finds zero salon references.
- [x] Phase 1–6 regression run has zero failures.

## Automated test runs

Full regression command:

```bash
EMBEDDING_BACKEND=local .venv/bin/python -m pytest -v \
  backend/tests/test_phase1_core.py backend/tests/test_phase2_tools.py \
  backend/tests/test_phase3_memory.py backend/tests/test_phase4_agent.py \
  backend/tests/test_phase5_scheduler.py backend/tests/test_phase6_salon.py
```

```text
collected 33 items
[Phase 1–5: 27 tests] PASSED
backend/tests/test_phase6_salon.py::test_bulk_import_creates_valid_rows_and_reports_malformed_row PASSED
backend/tests/test_phase6_salon.py::test_generate_outreach_script_is_registered_and_guarded PASSED
backend/tests/test_phase6_salon.py::test_log_interaction_writes_interaction_and_memory PASSED
backend/tests/test_phase6_salon.py::test_daily_plan_honors_playbook_seven_day_exclusion PASSED
backend/tests/test_phase6_salon.py::test_salon_crud_interaction_edges_and_duplicate_constraint PASSED
backend/tests/test_phase6_salon.py::test_cadence_parser_and_phone_db_constraint PASSED
============================== 33 passed in 0.91s ==============================
```

After adding Persian-digit support and safer serialized validation errors, Phase 6 was rerun:

```text
collected 6 items
6 passed in 0.19s
```

## Core isolation verification

```bash
grep -RniE 'salon|سالن' backend/app/agent backend/app/tools/registry.py backend/app/memory
```

Actual result:

```text
No salon-specific references found.
```

## Manual API check

Actual excerpts:

```text
$ curl -X POST /api/salons/import -d ...
{"created_count":2,"error_count":1,
 "created":[{"id":1,"name":"سالن نیلوفر",...},{"id":2,"name":"سالن رویا",...}],
 "errors":[{"index":1,"row":{"name":"ردیف ناقص","city":"شیراز"},
             "errors":[{"loc":["phone"],"msg":"Field required","type":"missing"}]}]}

$ curl /api/salons
[{"id":2,"name":"سالن رویا",...},{"id":1,"name":"سالن نیلوفر",...}]

$ curl -X PATCH /api/salons/1 -d '{"status":"contacted"}'
{"id":1,"name":"سالن نیلوفر",...,"status":"contacted"}

$ curl -X POST /api/salons/1/interactions -d ...
{"id":1,"salon_id":1,"channel":"whatsapp","content":"معرفی خدمات رشد",
 "outcome":"درخواست اطلاعات","occurred_at":"2026-08-24T12:00:00",...}

$ curl /api/salons/1/interactions
[{"id":1,"salon_id":1,"channel":"whatsapp",...}]

$ curl '/api/salons/daily-plan?as_of=2026-08-27T12:00:00Z' | compact
[{"name":"سالن رویا","days_since_contact":null,"cadence_days":7}]
# سالن نیلوفر، با تماس ۳ روز قبل، به‌درستی حذف شده است.

$ curl /api/tools | select generate_outreach_script
{"name":"generate_outreach_script","requires_approval":true,"enabled":true,...}

$ curl -X POST /api/tools/generate_outreach_script/invoke -d ...
{"status":"needs_approval","tool_name":"generate_outreach_script","result":null,...}

$ curl -X DELETE /api/salons/2
HTTP_204
```

## Changes to earlier-phase code

Only application composition (`main.py`) imports and mounts the salon module. No salon code or references were added to `agent/`, `memory/`, or `tools/registry.py`. All prior tests were rerun.

## Known limitations

The script generator produces a deterministic Persian first draft. More nuanced copy can be added as a separate AI-backed module tool, but no silent placeholder exists in the current implementation.
