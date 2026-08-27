#!/usr/bin/env bash
# ====================================================================
# Setup script for running WITHOUT Docker on a Linux server.
# Run this ONCE after cloning the repo:
#     ./setup.sh
# ====================================================================
set -e

ROOT="$(cd "$(dirname "$0")" && pwd)"
cd "$ROOT"

echo "================================================"
echo "  موتور دوبله خودکار ویدیو — نصب بدون Docker"
echo "================================================"
echo ""

# --- 1. Check system tools ---
echo "[1/6] بررسی پیش‌نیازهای سیستمی..."
command -v python3 >/dev/null 2>&1 || { echo "❌ python3 نصب نیست. sudo apt install python3 python3-pip python3-venv"; exit 1; }
command -v ffmpeg >/dev/null 2>&1 || { echo "❌ ffmpeg نصب نیست. sudo apt install ffmpeg"; exit 1; }
command -v node >/dev/null 2>&1 || { echo "❌ node نصب نیست. https://nodejs.org را نصب کنید (نسخه ۲۰+)"; exit 1; }
echo "  ✓ python3 $(python3 --version 2>&1)"
echo "  ✓ ffmpeg $(ffmpeg -version 2>&1 | head -1 | awk '{print $3}')"
echo "  ✓ node $(node --version)"
if command -v bun >/dev/null 2>&1; then echo "  ✓ bun $(bun --version)"; fi
echo ""

# --- 2. Python virtual env + backend deps ---
echo "[2/6] نصب وابستگی‌های Python (backend)..."
if [ ! -d backend/.venv ]; then
  python3 -m venv backend/.venv
  echo "  • venv ساخته شد در backend/.venv"
fi
# shellcheck disable=SC1091
source backend/.venv/bin/activate
pip install --quiet --upgrade pip
pip install --quiet -r backend/requirements.txt
deactivate
echo "  ✓ وابستگی‌های backend نصب شدند"
echo ""

# --- 3. Frontend deps ---
echo "[3/6] نصب وابستگی‌های Node (frontend)..."
if command -v bun >/dev/null 2>&1; then
  bun install --silent
  echo "  ✓ با bun نصب شد"
else
  npm install --silent
  echo "  ✓ با npm نصب شد"
fi
echo ""

# --- 4. .env ---
echo "[4/6] تنظیم فایل .env..."
if [ ! -f backend/.env ]; then
  cp backend/.env.example backend/.env
  echo "  ✓ backend/.env از .env.example ساخته شد"
  echo "  ⚠️  لطفاً کلید GEMINI_API_KEY خود را در backend/.env وارد کنید"
  echo "     یا می‌توانید بعداً از طریق صفحه‌ی 'تنظیمات' در UI آن را وارد کنید."
else
  echo "  ✓ backend/.env از قبل وجود دارد"
fi
echo ""

# --- 5. Whisper model pre-download (optional but recommended) ---
echo "[5/6] (اختیاری) پیش‌دانلود مدل Whisper..."
# shellcheck disable=SC1091
source backend/.venv/bin/activate
echo "  این مرحله ممکن است چند دقیقه طول بکشد (یک‌بار، ~50-150 MB)..."
python3 -c "
try:
    from faster_whisper import WhisperModel
    print('  • در حال دانلود/بارگذاری مدل base (CPU/int8)...')
    WhisperModel('base', device='cpu', compute_type='int8')
    print('  ✓ مدل Whisper آماده است')
except Exception as e:
    msg = str(e)[:120]
    if '429' in msg or 'Too Many' in msg:
        print('  ⚠️  HuggingFace موقتاً درخواست شما را محدود کرده (429).')
        print('      مدل در اولین اجرای واقعی دانلود خواهد شد، یا بعداً تلاش کنید.')
    else:
        print(f'  ⚠️  نتوانستیم مدل را پیش‌دانلود کنیم: {msg}')
        print('      این مشکل در اولین اجرای job ظاهر خواهد شد.')
" 2>&1 | tail -8
deactivate
echo ""

# --- 6. Done ---
echo "[6/6] راه‌اندازی کامل شد!"
echo ""
echo "================================================"
echo "  نحوه‌ی اجرا:"
echo "================================================"
echo ""
echo "  ترمینال ۱ — اجرای backend:"
echo "    cd backend"
echo "    source .venv/bin/activate"
echo "    python -m uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload"
echo ""
echo "  ترمینال ۲ — اجرای frontend:"
echo "    bun run dev"
echo "    (یا: npm run dev)"
echo ""
echo "  سپس مرورگر را روی http://localhost:3000 باز کنید."
echo ""
echo "  برای تنظیم کلید Gemini:"
echo "    ۱) ویرایش backend/.env و قرار دادن GEMINI_API_KEY"
echo "       یا"
echo "    ۲) در UI روی دکمه‌ی 'تنظیمات' کلیک کرده و کلید را وارد کنید"
echo "       (فقط در حافظه نگه داشته می‌شود)"
echo ""
echo "================================================"
