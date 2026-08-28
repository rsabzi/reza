#!/usr/bin/env bash
set -Eeuo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$ROOT"
PYTHON_BIN="${PYTHON:-python3}"

echo "[1/7] Checking Python 3.10+..."
command -v "$PYTHON_BIN" >/dev/null 2>&1 || { echo "ERROR: $PYTHON_BIN was not found." >&2; exit 1; }
"$PYTHON_BIN" - <<'PY'
import sys
if sys.version_info < (3, 10):
    raise SystemExit(f"ERROR: Python 3.10+ is required; found {sys.version.split()[0]}")
print(f"      Python {sys.version.split()[0]} OK")
PY

echo "[2/7] Checking Node.js and npm..."
command -v node >/dev/null 2>&1 || { echo "ERROR: Node.js was not found." >&2; exit 1; }
command -v npm >/dev/null 2>&1 || { echo "ERROR: npm was not found." >&2; exit 1; }
node -e 'const major=Number(process.versions.node.split(".")[0]); if(major<20){console.error(`ERROR: Node.js 20+ is required; found ${process.versions.node}`);process.exit(1)} console.log(`      Node.js ${process.versions.node} OK`)'

echo "[3/7] Creating Python virtual environment..."
if [[ ! -x .venv/bin/python ]]; then
    "$PYTHON_BIN" -m venv .venv
    echo "      Created .venv"
else
    echo "      Existing .venv reused"
fi

echo "[4/7] Installing Backend dependencies..."
.venv/bin/python -m pip install --disable-pip-version-check --quiet --upgrade pip
.venv/bin/python -m pip install --disable-pip-version-check --quiet -r backend/requirements.txt
echo "      Backend dependencies ready"

echo "[5/7] Installing Frontend dependencies from lockfile..."
npm ci --prefix frontend --no-audit --no-fund --silent
echo "      Frontend dependencies ready"

echo "[6/7] Building unified Dashboard assets..."
npm run build --prefix frontend --silent
echo "      Production Dashboard ready"

echo "[7/7] Preparing local configuration..."
if [[ ! -f .env ]]; then
    cp .env.example .env
    echo "      Created .env from .env.example"
else
    echo "      Existing .env preserved"
fi

cat <<'MSG'

Setup complete.
- Start both services: ./start_app.sh
- Dashboard:           http://127.0.0.1:8000
- API documentation:   http://127.0.0.1:8000/docs
- Gemini: open Dashboard > Settings and securely add/validate your key.
MSG
