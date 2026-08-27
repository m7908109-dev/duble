# راهنمای نصب روی سرور (Deployment Guide)

این سند نحوه‌ی نصب و راه‌اندازی «موتور دوبله خودکار ویدیو» روی سرور شخصی شما را شرح می‌دهد.

---

## فهرست

1. [پیش‌نیازها](#پیش‌نیازها)
2. [روش ۱: Docker (توصیه‌شده)](#روش-۱-docker-توصیهشده)
3. [روش ۲: نصب دستی روی Linux](#روش-۲-نصب-دستی-روی-linux)
4. [قرار دادن پشت Nginx با HTTPS](#قرار-دادن-پشت-nginx-با-https)
5. [متغیرهای محیطی](#متغیرهای-محیطی)
6. [چک‌لیست production](#چکلیست-production)
7. [مدیریت و نگهداری](#مدیریت-و-نگهداری)
8. [رفع اشکال](#رفع-اشکال)

---

## پیش‌نیازها

### سخت‌افزار حداقلی

| منبع | حداقل | توصیه‌شده |
|---|---|---|
| CPU | ۲ هسته | ۴ هسته |
| RAM | ۴ GB | ۸ GB |
| دیسک | ۱۰ GB | ۲۰+ GB (برای ویدیوها) |
| GPU | لازم نیست (CPU-only) | اختیاری (سرعت Whisper بالاتر) |

### نرم‌افزار

- **OS**: Ubuntu 22.04+ / Debian 12+ (یا هر توزیع لینوکس مدرن)
- **Docker 24+** و **Docker Compose v2** (برای روش Docker)
- یا برای روش دستی:
  - **Python 3.11+**
  - **FFmpeg** (شامل `ffmpeg` و `ffprobe`)
  - **Node.js 20+** و **bun** (یا npm)
- **کلید API رایگان Gemini** از [Google AI Studio](https://aistudio.google.com/app/apikey)
- اتصال اینترنت (دانلود ویدیو، فراخوانی Gemini، edge-tts)

> توجه: در اولین اجرا، مدل Whisper از HuggingFace دانلود می‌شود (یک‌بار، حدود ۵۰–۱۵۰ مگابایت بسته به اندازه‌ی مدل). اگر سرور شما به `huggingface.co` دسترسی ندارد، مدل را روی دستگاهی با دسترسی دانلود کرده و به `~/.cache/huggingface/hub/models--Systran--faster-whisper-base/` کپی کنید.

---

## روش ۱: Docker (توصیه‌شده)

ساده‌ترین راه. همه‌چیز (Python + FFmpeg + Node + وابستگی‌ها) در دو container اجرا می‌شود.

### مرحله ۱: دریافت فایل‌ها

فایل `dubbing-engine.tar.gz` را روی سرور کپی و باز کنید:

```bash
# فایل را روی سرور آپلود کنید (با scp یا روش دلخواه)
scp dubbing-engine.tar.gz user@your-server:/opt/

# روی سرور:
cd /opt
tar -xzf dubbing-engine.tar.gz
cd dubbing-engine
```

### مرحله ۲: نصب Docker (اگر ندارید)

```bash
# Ubuntu/Debian
curl -fsSL https://get.docker.com | sh
sudo usermod -aG docker $USER
# logout/login مجدد برای اعمال گروه docker
```

### مرحله ۳: تنظیم کلید Gemini

```bash
cp backend/.env.example backend/.env
nano backend/.env
# مقدار GEMINI_API_KEY را پر کنید
```

یا فقط به‌صورت متغیر محیطی موقع اجرا:

```bash
export GEMINI_API_KEY="AIza...کلید شما..."
```

### مرحله ۴: build و اجرا

```bash
docker compose up --build -d
```

- `backend` روی پورت `8000` و `frontend` روی پورت `3000` اجرا می‌شوند.
- volume به‌نام `dubbing-storage` برای ماندگاری jobها و دیتابیس ساخته می‌شود.

### مرحله ۵: بررسی

```bash
# سلامت backend
curl http://localhost:8000/api/health

# باز کردن frontend
# مرورگر را روی http://YOUR-SERVER-IP:3000 باز کنید
```

### دستورات مفید Docker

```bash
docker compose logs -f           # مشاهده‌ی log زنده
docker compose logs -f backend   # فقط backend
docker compose ps                # وضعیت containerها
docker compose restart backend   # restart فقط backend
docker compose down              # توقف
docker compose up --build -d     # rebuild بعد از تغییر کد
```

---

## روش ۲: نصب دستی روی Linux

اگر نمی‌خواهید از Docker استفاده کنید.

### مرحله ۱: نصب پیش‌نیازهای سیستمی

```bash
sudo apt update
sudo apt install -y python3 python3-pip python3-venv ffmpeg curl git

# Node.js 20 و bun
curl -fsSL https://deb.nodesource.com/setup_20.x | sudo -E bash -
sudo apt install -y nodejs

# bun
curl -fsSL https://bun.sh/install | bash
source ~/.bashrc
```

بررسی:

```bash
python3 --version    # 3.11+
ffmpeg -version
node --version      # 20+
bun --version
```

### مرحله ۲: دریافت و باز کردن فایل‌ها

```bash
cd /opt
tar -xzf dubbing-engine.tar.gz
cd dubbing-engine
```

### مرحله ۳: نصب وابستگی‌های backend

```bash
cd backend
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
deactivate
cd ..
```

### مرحله ۴: نصب وابستگی‌های frontend

```bash
bun install   # یا: npm install
```

### مرحله ۵: تنظیم .env

```bash
cp backend/.env.example backend/.env
nano backend/.env
```

حداقل باید این مقدار را تنظیم کنید:

```ini
GEMINI_API_KEY=AIza...کلید شما...
# بقیه را می‌توانید به‌صورت پیش‌فرض رها کنید
```

### مرحله ۶: build فرانت‌اند برای production

```bash
bun run build
# خروجی در .next/standalone ذخیره می‌شود
```

### مرحله ۷: اجرای backend به‌صورت سرویس دائمی (systemd)

فایل `/etc/systemd/system/dubbing-backend.service` بسازید:

```bash
sudo nano /etc/systemd/system/dubbing-backend.service
```

محتوا (مسیر `/opt/dubbing-engine` را با مسیر واقعی خودتان جایگزین کنید):

```ini
[Unit]
Description=Automatic Video Dubbing Engine — Backend
After=network.target

[Service]
Type=simple
User=YOUR_USERNAME
WorkingDirectory=/opt/dubbing-engine/backend
Environment=PYTHONPATH=/opt/dubbing-engine/backend
EnvironmentFile=/opt/dubbing-engine/backend/.env
ExecStart=/opt/dubbing-engine/backend/.venv/bin/python -m uvicorn app.main:app --host 127.0.0.1 --port 8000 --workers 1
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
```

فعال‌سازی:

```bash
sudo systemctl daemon-reload
sudo systemctl enable --now dubbing-backend
sudo systemctl status dubbing-backend   # بررسی وضعیت
```

### مرحله ۸: اجرای frontend به‌صورت سرویس دائمی

فایل `/etc/systemd/system/dubbing-frontend.service`:

```ini
[Unit]
Description=Automatic Video Dubbing Engine — Frontend
After=network.target dubbing-backend.service

[Service]
Type=simple
User=YOUR_USERNAME
WorkingDirectory=/opt/dubbing-engine
Environment=NODE_ENV=production
Environment=PORT=3000
Environment=HOSTNAME=0.0.0.0
ExecStart=/usr/bin/bun .next/standalone/server.js
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
```

> اگر `bun` در مسیر دیگری است، مسیر `ExecStart` را اصلاح کنید (مثلاً `/home/USER/.bun/bin/bun`).
> اگر از npm استفاده می‌کنید: `ExecStart=/usr/bin/node .next/standalone/server.js`

فعال‌سازی:

```bash
sudo systemctl daemon-reload
sudo systemctl enable --now dubbing-frontend
sudo systemctl status dubbing-frontend
```

### مرحله ۹: باز کردن پورت‌ها در فایروال

```bash
sudo ufw allow 3000/tcp
sudo ufw allow 8000/tcp   # فقط اگر مستقیم می‌خواهید backend را تست کنید
sudo ufw status
```

### مرحله ۱۰: تست

```bash
curl http://localhost:8000/api/health   # backend
curl http://localhost:3000/              # frontend
```

مرورگر را روی `http://YOUR-SERVER-IP:3000` باز کنید.

---

## قرار دادن پشت Nginx با HTTPS

برای سرو روی پورت ۸۰/۴۴۳ با دامنه‌ی اختصاصی و گواهی SSL رایگان (Let's Encrypt).

### نصب Nginx و Certbot

```bash
sudo apt install -y nginx certbot python3-certbot-nginx
```

### پیکربندی Nginx

فایل `/etc/nginx/sites-available/dubbing`:

```nginx
server {
    listen 80;
    server_name dub.example.com;   # دامنه‌ی خودتان

    # افزایش حداکثر حجم آپلود (در صورت نیاز)
    client_max_body_size 2G;

    # API و SSE → backend
    location /api/ {
        proxy_pass http://127.0.0.1:8000;
        proxy_http_version 1.1;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;

        # پشتیبانی از SSE — مهم!
        proxy_buffering off;
        proxy_cache off;
        proxy_read_timeout 86400s;
        proxy_send_timeout 86400s;
    }

    # همه‌ی چیز دیگر → frontend
    location / {
        proxy_pass http://127.0.0.1:3000;
        proxy_http_version 1.1;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
    }
}
```

فعال‌سازی و گرفتن گواهی SSL:

```bash
sudo ln -s /etc/nginx/sites-available/dubbing /etc/nginx/sites-enabled/
sudo nginx -t
sudo systemctl reload nginx

# گواهی SSL رایگان
sudo certbot --nginx -d dub.example.com
```

حالا اپلیکیشن روی `https://dub.example.com` در دسترس است.

> نکته‌ی مهم برای SSE: خط `proxy_buffering off;` الزامی است، وگرنه progress زنده کار نمی‌کند.

---

## متغیرهای محیطی

تمام متغیرها در `backend/.env` (از `.env.example` کپی کنید):

| متغیر | پیش‌فرض | توضیح |
|---|---|---|
| `GEMINI_API_KEY` | (خالی) | **الزامی**. کلید API رایگان Gemini. |
| `GEMINI_MODEL` | `gemini-2.0-flash` | مدل Gemini برای ترجمه. |
| `WHISPER_MODEL` | `base` | `tiny` \| `base` \| `small` \| `medium` \| `large-v3` یا `auto` (انتخاب هوشمند بر اساس RAM). |
| `WHISPER_COMPUTE_TYPE` | `int8` | CPU: `int8`، GPU: `float16`. |
| `WHISPER_DEVICE` | `auto` | `cpu` \| `cuda` \| `auto`. |
| `TTS_PROVIDER` | `edge` | `edge` (edge-tts) یا `piper` (کاملاً local). |
| `TTS_DEFAULT_VOICE` | `fa-IR-DilaraNeural` | صدای پیش‌فرض edge-tts. |
| `PIPER_MODEL_PATH` | (خالی) | مسیر مدل Piper (فقط هنگام `TTS_PROVIDER=piper`). |
| `HOST` / `PORT` | `0.0.0.0` / `8000` | آدرس backend. |
| `STORAGE_DIR` | `./storage` | مسیر ذخیره‌سازی jobها و دیتابیس. |
| `MAX_CONCURRENT_JOBS` | `1` | حداکثر job همزمان (روی RAM کم، ۱ نگه دارید). |
| `MAX_VIDEO_DURATION_SECONDS` | `0` | حداکثر مدت ویدیو (ثانیه، ۰ = نامحدود). |
| `MAX_DOWNLOAD_MB` | `2048` | حداکثر حجم دانلود. |
| `OUTPUT_FORMAT` | `mp4` | فرمت خروجی. |
| `OUTPUT_CRF` | `23` | کیفیت encode ویدیو (کمتر = با کیفیت‌تر). |
| `SYNC_MIN_SPEED` / `SYNC_MAX_SPEED` | `0.80` / `1.30` | محدوده‌ی تغییر سرعت صدا. |

> کلید Gemini می‌تواند به‌جای `.env` از طریق صفحه‌ی «تنظیمات» در UI هم وارد شود (فقط در حافظه‌ی پردازش نگه داشته می‌شود، روی دیسک ذخیره نمی‌شود).

---

## چک‌لیست production

قبل از بردن به محیط واقعی، مطمئن شوید:

- [ ] کلید `GEMINI_API_KEY` تنظیم شده.
- [ ] `MAX_CONCURRENT_JOBS` متناسب با RAM سرور تنظیم شده (۱ برای ۴GB، ۲ برای ۸GB+).
- [ ] پوشه‌ی `storage/` روی یک disk با فضای کافی قرار دارد.
- [ ] اگر از Docker استفاده می‌کنید، volume `dubbing-storage` پایدار است (`docker volume inspect dubbing-storage`).
- [ ] اگر از Nginx استفاده می‌کنید، `proxy_buffering off;` برای مسیر `/api/` فعال است.
- [ ] فایروال فقط پورت‌های ۸۰/۴۴۳ را باز کرده‌اند (۳۰۰۰ و ۸۰۰۰ فقط داخلی).
- [ ] گواهی SSL با certbot تمدید خودکار دارد (`sudo certbot renew --dry-run`).
- [ ] Log را بررسی کرده‌اید: `docker compose logs` یا `journalctl -u dubbing-backend -f`.

---

## مدیریت و نگهداری

### پاک‌سازی فایل‌های موقت jobها

هر job فایل‌های موقت در `storage/jobs/{job_id}/` می‌سازد. برای آزاد کردن فضا:

```bash
# روش Docker: حجم مصرفی volume
docker compose exec backend du -sh /app/storage/jobs

# پاک‌سازی jobهای قدیمی (مثلاً قدیمی‌تر از ۷ روز)
find /opt/dubbing-engine/backend/storage/jobs -type d -mtime +7 -exec rm -rf {} +
```

API هم موجود است:

```bash
curl -X POST http://localhost:8000/api/jobs/{job_id}/cleanup?keep_output=true
```

### بک‌اپ دیتابیس

```bash
# روش Docker
docker compose exec backend cp /app/storage/dubbing.db /tmp/dubbing.db.bak

# روش دستی
cp /opt/dubbing-engine/backend/storage/dubbing.db /backup/dubbing-$(date +%F).db
```

### به‌روزرسانی پروژه

```bash
# فایل جدید را جایگزین کنید، سپس:
# روش Docker:
docker compose up --build -d

# روش دستی:
cd /opt/dubbing-engine/backend && source .venv/bin/activate && pip install -r requirements.txt
cd /opt/dubbing-engine && bun install && bun run build
sudo systemctl restart dubbing-backend dubbing-frontend
```

### بررسی logها

```bash
# Docker
docker compose logs -f backend
docker compose logs -f frontend

# systemd
sudo journalctl -u dubbing-backend -f
sudo journalctl -u dubbing-frontend -f
```

> کلید API هرگز در log چاپ نمی‌شود (یک RedactingFormatter همه‌ی logها را فیلتر می‌کند).

---

## رفع اشکال

### «GEMINI_API_KEY is not set»
کلید را در `backend/.env` یا از طریق UI تنظیم کنید. backend را restart کنید.

### مدل Whisper دانلود نمی‌شود (خطای 429 HuggingFace)
HuggingFace ممکن است به‌صورت موقت IP شما را محدود کند. راه‌حل‌ها:
- چند دقیقه صبر و تلاش مجدد.
- مدل را با پروکسی/VPN دانلود و به `~/.cache/huggingface/hub/` کپی کنید.
- مدل سبک‌تر استفاده کنید: `WHISPER_MODEL=tiny`.

### «edge-tts synthesis failed»
- مطمئن شوید سرور به اینترنت دسترسی دارد (edge-tts نیاز به سرویس آنلاین دارد).
- برای کاملاً آفلاین، `TTS_PROVIDER=piper` تنظیم و یک مدل Piper دانلود کنید.

### ویدیوی خروجی پخش نمی‌شود
- مطمئن شوید `ffmpeg` روی سرور نصب است.
- برای روش دستی، `storage/jobs/{job_id}/output/` را بررسی کنید.

### SSE کار نمی‌کند (progress آپدیت نمی‌شود)
- اگر پشت Nginx هستید: `proxy_buffering off;` را در `location /api/` فعال کنید.
- اگر پشت proxy دیگر: `X-Accel-Buffering: no` را اضافه کنید یا buffer را غیرفعال کنید.

### خطای «Out of memory» هنگام render
- `MAX_CONCURRENT_JOBS=1` نگه دارید.
- ویدیوها به‌صورت پیش‌فرض 720p دانلود می‌شوند (مصرف RAM پایین).
- مدل Whisper سبک‌تر: `WHISPER_MODEL=tiny` یا `base`.

### خطای «Max concurrent jobs reached»
یا صبر کنید تا job فعلی تمام شود، یا `MAX_CONCURRENT_JOBS` را در `.env` افزایش دهید و restart کنید.

---

سوالی بود، به README.md مراجعه کنید یا logها را بررسی کنید.
