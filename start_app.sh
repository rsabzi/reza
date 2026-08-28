#!/usr/bin/env bash
set -Eeuo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$ROOT"
APP_PORT="${APP_PORT:-${BACKEND_PORT:-8000}}"

[[ -x .venv/bin/python ]] || { echo "ERROR: Run ./setup.sh first (.venv is missing)." >&2; exit 1; }
[[ -d frontend/node_modules ]] || { echo "ERROR: Run ./setup.sh first (frontend dependencies are missing)." >&2; exit 1; }

ENV_ARGS=()
if [[ -f .env ]]; then
    ENV_ARGS=(--env-file "$ROOT/.env")
fi

cleanup() {
    trap - EXIT INT TERM
    echo
    echo "Stopping Agent Core..."
    kill "${APP_PID:-}" 2>/dev/null || true
    wait "${APP_PID:-}" 2>/dev/null || true
}
trap cleanup EXIT INT TERM

echo "Building current Dashboard assets..."
npm run build --prefix frontend --silent

echo "Starting unified Dashboard + API on 0.0.0.0:${APP_PORT}..."
.venv/bin/python -m uvicorn backend.app.main:app \
    --host 0.0.0.0 --port "$APP_PORT" "${ENV_ARGS[@]}" &
APP_PID=$!

echo "Dashboard: http://127.0.0.1:${APP_PORT}"
echo "API docs: http://127.0.0.1:${APP_PORT}/docs"
echo "One origin, one process; no browser proxy is required."
echo "Press Ctrl+C to stop."

wait "$APP_PID"
