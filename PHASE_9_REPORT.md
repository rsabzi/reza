# Phase 9 Report — Local Setup & Autostart

## Built

- Idempotent `setup.sh` and `setup.bat` with version checks, virtualenv, locked Frontend install, and preserved local config.
- `start_app.sh` starts both processes, proxies Frontend API to the selected Backend port, and terminates both children together.
- `start_app.bat` starts named Backend/Frontend windows and supports custom ports.
- `.env.example` documents Gemini, embedding backend, timezone, and local database without storing credentials.
- Detailed Windows Task Scheduler and Startup-folder instructions in `docs/WINDOWS_STARTUP.md`.

## Acceptance criteria

- [x] Setup run in a clean copied tree with no `.venv`, `node_modules`, or `.env`; no manual input was needed.
- [x] Start script launched Backend and Frontend simultaneously on clean-install ports.
- [x] Backend health, Frontend HTML, Frontend→Backend proxy, and a real Task POST all responded.

## Clean-environment setup simulation

A fresh copy was created and finally rechecked at `/tmp/reza-setup-smoke-final`, explicitly excluding `.venv`, `frontend/node_modules`, `.env`, databases, build output, and Git metadata.

Command:

```bash
cd /tmp/reza-setup-smoke-final && ./setup.sh
```

Full actual terminal output:

```text
--- clean-copy preconditions ---
.venv absent: yes
node_modules absent: yes
.env absent: yes
--- setup.sh full output ---
[1/6] Checking Python 3.10+...
      Python 3.11.2 OK
[2/6] Checking Node.js and npm...
      Node.js 22.22.3 OK
[3/6] Creating Python virtual environment...
      Created .venv
[4/6] Installing Backend dependencies...
      Backend dependencies ready
[5/6] Installing Frontend dependencies from lockfile...
      Frontend dependencies ready
[6/6] Preparing local configuration...
      Created .env from .env.example

Setup complete.
- Start both services: ./start_app.sh
- Dashboard:           http://127.0.0.1:5173
- API documentation:   http://127.0.0.1:8000/docs
- Optional: set GEMINI_API_KEY in .env for real AI planning.
```

## Clean-install start verification

Command (custom ports avoid conflict with the main live preview):

```bash
BACKEND_PORT=18000 FRONTEND_PORT=15173 /tmp/reza-setup-smoke/start_app.sh
```

Actual startup output:

```text
Starting Agent Core API on 0.0.0.0:18000...
Starting Persian dashboard on 0.0.0.0:15173...
Dashboard: http://127.0.0.1:15173
API docs: http://127.0.0.1:18000/docs
Press Ctrl+C to stop both services.

> agent-core-dashboard@1.0.0 dev
> vite --host 0.0.0.0 --port 15173
VITE v8.2.2 ready

INFO: Loading environment from '/tmp/reza-setup-smoke/.env'
INFO: Application startup complete.
INFO: Uvicorn running on http://0.0.0.0:18000
```

Actual requests/responses:

```text
$ curl -s -i http://127.0.0.1:18000/api/health
HTTP/1.1 200 OK
content-type: application/json

{"status":"ok","service":"Agent Core"}

$ curl -s -o /dev/null -w 'HTTP_%{http_code} content_type=%{content_type}' http://127.0.0.1:15173/
HTTP_200 content_type=text/html

$ curl -s http://127.0.0.1:15173/api/health
{"status":"ok","service":"Agent Core"}

$ curl -s -X POST http://127.0.0.1:15173/api/tasks \
    -H 'content-type: application/json' -d '{"title":"Clean install smoke task"}'
{"id":1,"title":"Clean install smoke task","status":"pending",...}
```

Stopping the parent process produced:

```text
Stopping Agent Core services...
INFO: Shutting down
INFO: Application shutdown complete.
```

## Re-run commands

```bash
./setup.sh
./start_app.sh
```

Windows:

```bat
setup.bat
start_app.bat
```

## Post-delivery unified-server hardening

The runtime was later simplified to one process and one origin: FastAPI now serves both the production React build and `/api`. Setup builds the frontend, and both start scripts launch the unified app. This removes the Vite proxy from end-user runtime and prevents Preview-only API hangs. Vite remains available for frontend development and tests.

## Known limitations

The Windows batch script was structurally reviewed but cannot be executed on this Linux runner. The equivalent shell workflow and unified Uvicorn service were tested; root HTML, JS assets, API health, system status, and Swagger all returned HTTP 200.
