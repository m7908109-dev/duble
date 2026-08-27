#!/usr/bin/env bash
# Start the Automatic Video Dubbing Engine backend.
# Usage:  ./start.sh   (from the backend/ directory)

set -e

cd "$(dirname "$0")"

# Create the venv-local .env from .env.example if missing.
if [ ! -f .env ]; then
  cp .env.example .env
  echo "[start.sh] Created .env from .env.example — edit it to add GEMINI_API_KEY."
fi

# Install dependencies if fastapi isn't importable.
python3 -c "import fastapi" 2>/dev/null || pip3 install -r requirements.txt

export PYTHONUNBUFFERED=1
export PYTHONPATH="$(pwd):${PYTHONPATH:-}"

echo "[start.sh] Starting backend on http://0.0.0.0:${PORT:-8000}"
exec python3 -m uvicorn app.main:app \
  --host "${HOST:-0.0.0.0}" \
  --port "${PORT:-8000}" \
  --workers 1
