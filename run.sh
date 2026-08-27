#!/usr/bin/env bash
# ====================================================================
# Start script — runs backend + frontend WITHOUT Docker.
# Use AFTER running ./setup.sh once.
# Usage:  ./run.sh
# Stop:   Ctrl+C  (هر دو سرویس متوقف می‌شوند)
# ====================================================================
set -e

ROOT="$(cd "$(dirname "$0")" && pwd)"
cd "$ROOT"

echo "================================================"
echo "  موتور دوبله خودکار ویدیو — اجرا (بدون Docker)"
echo "================================================"
echo ""

# Make sure .env exists
if [ ! -f backend/.env ]; then
  cp backend/.env.example backend/.env
  echo "⚠️  backend/.env ساخته شد. لطفاً GEMINI_API_KEY را در آن وارد کنید."
fi

# --- Start backend (port 8000) ---
echo "[1/2] اجرای backend روی پورت 8000..."
(
  cd "$ROOT/backend"
  # shellcheck disable=SC1091
  source .venv/bin/activate 2>/dev/null || true
  PYTHONPATH="$ROOT/backend" \
  PORT=8000 \
  uvicorn app.main:app --host 0.0.0.0 --port 8000 --workers 1 \
    > "$ROOT/backend/backend.log" 2>&1 &
  BACKEND_PID=$!
  echo "  ✓ backend PID: $BACKEND_PID"
)

# Give the backend a moment to boot
sleep 3

# --- Start frontend (port 3000) ---
echo "[2/2] اجرای frontend روی پورت 3000..."
(
  cd "$ROOT"
  if command -v bun >/dev/null 2>&1; then
    bun run dev > "$ROOT/dev.log" 2>&1 &
  else
    npm run dev > "$ROOT/dev.log" 2>&1 &
  fi
  FRONTEND_PID=$!
  echo "  ✓ frontend PID: $FRONTEND_PID"
)

echo ""
echo "================================================"
echo "  سرویس‌ها در حال اجرا هستند:"
echo "================================================"
echo "  • Backend:  http://localhost:8000  (log: backend/backend.log)"
echo "  • Frontend: http://localhost:3000   (log: dev.log)"
echo ""
echo "  مرورگر را روی http://localhost:3000 باز کنید."
echo ""
echo "  برای توقف: Ctrl+C"
echo "================================================"
echo ""

# Wait for both child processes; Ctrl+C kills both
wait
