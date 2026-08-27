# موتور دوبله خودکار ویدیو (Automatic Video Dubbing Engine)

یک وب‌اپلیکیشن کامل و **متن‌باز و رایگان** برای دریافت ویدیوی YouTube، استخراج گفتار با **Whisper**، ترجمه با **Gemini**، تولید صدای دوبله با موتور **TTS رایگان**، هماهنگ‌سازی زمان‌بندی صدا، و تحویل ویدیوی دوبله‌شده نهایی.

> Open-source • Free • CPU-only friendly • Works on GitHub Codespaces

---

## فهرست

1. [معماری سیستم](#معماری-سیستم)
2. [ساختار پروژه](#ساختار-پروژه)
3. [پیش‌نیازها](#پیش‌نیازها)
4. [نصب و اجرا](#نصب-و-اجرا)
5. [Environment Variables](#environment-variables)
6. [API Reference](#api-reference)
7. [پایپ‌لاین پردازش](#پایپ‌لاین-پردازش)
8. [ماژولار بودن و تعویض موتورها](#ماژولار-بودن-و-تعویض-موتورها)
9. [هماهنگ‌سازی صدا (Sync)](#هماهنگ‌سازی-صدا-sync)
10. [Resume / Recovery](#resume--recovery)
11. [امنیت](#امنیت)
12. [Docker](#docker)
13. [تست‌ها](#تست‌ها)
14. [نکات منابع Codespaces](#نکات-منابع-codespaces)

---

## معماری سیستم

```
YouTube URL
   │
   ▼
┌──────────────────┐
│ YouTube Service  │  yt-dlp (metadata + download)
└──────────────────┘
   │
   ▼
┌──────────────────┐
│ FFmpeg           │  extract 16kHz mono WAV
└──────────────────┘
   │
   ▼
┌──────────────────┐
│ faster-whisper   │  STT → segments + timestamps
└──────────────────┘
   │
   ▼
┌──────────────────┐
│ Gemini (batch)   │  translation, IDs preserved
└──────────────────┘
   │
   ▼
┌──────────────────┐
│ TTS Adapter      │  edge-tts (default) | piper
└──────────────────┘
   │
   ▼
┌──────────────────┐
│ Synchronization  │  time-stretch + overlay → timeline
└──────────────────┘
   │
   ▼
┌──────────────────┐
│ FFmpeg (mux)     │  video copy + audio encode → MP4
└──────────────────┘
   │
   ▼
   Final dubbed video
```

**Hybrid deployment در این پروژه:**
- **Backend** (پایتون FastAPI) روی پورت `8000` — تمام منطق پردازش.
- **Frontend** (Next.js + React + Tailwind + shadcn/ui) روی پورت `3000` — رابط کاربری فارسی RTL با Dark Mode.
- Frontend با پشت‌میز (backend) از طریق `/api/*` (با `XTransformPort` یا از طریق rewrite در dev) صحبت می‌کند.

---

## ساختار پروژه

```
.
├── backend/                     # Python FastAPI backend
│   ├── app/
│   │   ├── main.py              # FastAPI app + startup + routes mount
│   │   ├── api/routes/          # video, jobs, settings, tts routes
│   │   ├── core/
│   │   │   ├── config.py        # pydantic-settings (env vars)
│   │   │   ├── security.py      # URL validation, path sanitization, redact
│   │   │   ├── logging.py       # redacting formatter
│   │   │   └── resources.py     # CPU/RAM/GPU detection
│   │   ├── services/
│   │   │   ├── youtube.py        # yt-dlp wrapper
│   │   │   ├── ffmpeg.py         # audio extraction, stretch, mix, mux
│   │   │   ├── transcription.py  # faster-whisper
│   │   │   ├── translation.py   # Gemini (batched, strict JSON)
│   │   │   ├── synchronization.py  # clips + timeline composition
│   │   │   ├── dubbing.py        # full pipeline orchestrator (resume-aware)
│   │   │   └── tts/
│   │   │       ├── base.py      # TTSProvider interface (ABC)
│   │   │       ├── edge.py      # edge-tts adapter
│   │   │       ├── piper.py      # piper adapter (truly local)
│   │   │       └── registry.py   # provider registration
│   │   ├── models/
│   │   │   ├── database.py       # aiosqlite + schema
│   │   │   └── job.py            # pydantic models + statuses
│   │   ├── workers/
│   │   │   └── job_manager.py    # in-process queue + SSE pub/sub
│   │   └── utils/
│   │       ├── paths.py          # JobPaths layout
│   │       └── timing.py         # sync math (pure, tested)
│   ├── tests/                   # unit + integration tests
│   ├── storage/jobs/{job_id}/    # per-job filesystem layout
│   ├── requirements.txt
│   ├── .env.example
│   ├── Dockerfile
│   ├── start.sh
│   ├── run.py
│   └── pytest.ini
├── src/                         # Next.js 16 frontend (App Router)
│   ├── app/
│   │   ├── layout.tsx           # RTL, Vazirmatn font, dark mode
│   │   ├── page.tsx             # main UI orchestrator
│   │   └── globals.css          # emerald theme, custom scrollbar
│   ├── components/dubbing/
│   │   ├── NewJobForm.tsx       # URL + inspect + dubbing settings
│   │   ├── JobDetail.tsx        # progress + transcript + output
│   │   ├── JobList.tsx          # dashboard of recent jobs
│   │   ├── ProgressSteps.tsx    # ✓ ● ○ stage indicators
│   │   ├── TranscriptView.tsx   # original | translation
│   │   └── SettingsDialog.tsx   # Gemini key + resource info
│   └── lib/dubbing-api.ts       # typed API client (SSE support)
├── docker-compose.yml
├── start.sh                     # one-command launcher
└── README.md
```

هر سرویس (YouTube/Whisper/Gemini/TTS/FFmpeg) Interface مشخص دارد و بدون تغییر بخش‌های دیگر قابل تعویض است.

---

## پیش‌نیازها

- **Python 3.11+** (تست‌شده با 3.12)
- **FFmpeg** (شامل `ffmpeg` و `ffprobe`)
- **Node.js 18+** و **bun** (یا npm) برای فرانت‌اند
- **کلید API رایگان Gemini** از [Google AI Studio](https://aistudio.google.com/app/apikey)
- اتصال اینترنت (برای دانلود ویدیو، فراخوانی Gemini، و edge-tts)

بررسی نصب بودن:
```bash
python3 --version
ffmpeg -version
bun --version   # یا npm --version
```

---

## نصب و اجرا

### روش ۱: اجرای محلی (توصیه‌شده برای Codespaces)

```bash
# ۱) کلون پروژه
git clone <repo-url>
cd automatic-video-dubbing-engine

# ۲) نصب وابستگی‌های Python
cd backend
pip install -r requirements.txt

# ۳) تنظیم کلید Gemini (یا از طریق UI در تنظیمات وارد کنید)
cp .env.example .env
# .env را باز کرده و GEMINI_API_KEY را پر کنید

# ۴) اجرای backend
cd ..
PYTHONPATH=backend python3 -m uvicorn app.main:app --host 0.0.0.0 --port 8000

# ۵) در ترمینال دیگر: اجرای frontend
bun run dev
```

یا با یک دستور:
```bash
./start.sh
```

سپس مرورگر را روی `http://localhost:3000` باز کنید.

### روش ۲: Docker

```bash
export GEMINI_API_KEY="your-key-here"
docker compose up --build
```

---

## Environment Variables

تمام متغیرها در `backend/.env` (از `.env.example` کپی کنید). API Key هرگز در کد، فایل git، log یا response API قرار نمی‌گیرد.

| متغیر | پیش‌فرض | توضیح |
|---|---|---|
| `GEMINI_API_KEY` | (خالی) | کلید API رایگان Gemini. می‌توانید از طریق UI هم وارد کنید. |
| `GEMINI_MODEL` | `gemini-2.0-flash` | مدل Gemini استفاده‌شده برای ترجمه. |
| `WHISPER_MODEL` | `base` | اندازه مدل Whisper: `tiny` \| `base` \| `small` \| `medium` \| `large-v3` یا `auto` برای انتخاب هوشمند. |
| `WHISPER_COMPUTE_TYPE` | `int8` | نوع محاسبات CTranslate2 (CPU: `int8`، GPU: `float16`). |
| `WHISPER_DEVICE` | `auto` | `cpu` \| `cuda` \| `auto`. |
| `TTS_PROVIDER` | `edge` | `edge` (edge-tts، پیش‌فرض) یا `piper` (کاملاً local). |
| `TTS_DEFAULT_VOICE` | `fa-IR-DilaraNeural` | صدای پیش‌فرض edge-tts برای فارسی. |
| `PIPER_MODEL_PATH` | (خالی) | مسیر فایل ONNX مدل Piper (فقط هنگام `TTS_PROVIDER=piper`). |
| `HOST` / `PORT` | `0.0.0.0` / `8000` | آدرس و پورت backend. |
| `STORAGE_DIR` | `./storage` | مسیر ذخیره‌سازی jobها و دیتابیس. |
| `MAX_CONCURRENT_JOBS` | `1` | حداکثر تعداد job همزمان (Codespaces: ۱). |
| `MAX_VIDEO_DURATION_SECONDS` | `0` | حداکثر مدت ویدیوی ورودی (ثانیه، ۰ = نامحدود). |
| `MAX_DOWNLOAD_MB` | `2048` | حداکثر حجم دانلود. |
| `OUTPUT_FORMAT` | `mp4` | فرمت خروجی نهایی. |
| `OUTPUT_CRF` | `23` | کیفیت encode ویدیو (مقدار کمتر = کیفیت بالاتر). |
| `SYNC_MIN_SPEED` / `SYNC_MAX_SPEED` | `0.80` / `1.30` | محدوده تغییر سرعت صدا برای هماهنگ‌سازی. |

> توجه: مدل Whisper در اولین اجرا از HuggingFace دانلود می‌شود (یک‌بار، حدود ۵۰–۱۵۰ مگابایت بسته به اندازه). این نیازمند دسترسی به `huggingface.co` است.

---

## API Reference

| متد و مسیر | توضیح |
|---|---|
| `POST /api/video/inspect` | دریافت metadata ویدیو (بدون دانلود): عنوان، تامنیل، مدت، کیفیت‌ها. |
| `POST /api/jobs` | ساخت job دوبله. بدنه: `CreateJobRequest`. خروجی: `{job_id, status}`. |
| `GET /api/jobs` | فهرست jobهای اخیر. |
| `GET /api/jobs/{job_id}` | وضعیت job. |
| `GET /api/jobs/{job_id}/events` | **SSE** stream زنده‌ی وضعیت. |
| `POST /api/jobs/{job_id}/cancel` | لغو job. |
| `GET /api/jobs/{job_id}/video` | دانلود/پخش ویدیوی دوبله‌شده (پس از تکمیل). |
| `GET /api/jobs/{job_id}/transcript` | متن استخراج‌شده با Whisper (JSON). |
| `GET /api/jobs/{job_id}/translation` | ترجمه‌ها (JSON). |
| `POST /api/jobs/{job_id}/cleanup` | پاک‌سازی فایل‌های موقت. |
| `GET /api/settings` | تنظیمات فعلی + فهرست صداها + اطلاعات منابع. |
| `PUT /api/settings` | تنظیم کلید Gemini (در حافظه، نه روی دیسک). |
| `GET /api/tts/providers` | فهرست providerهای TTS. |
| `GET /api/tts/voices` | فهرست صداها (با فیلتر `provider` و `language`). |
| `GET /api/languages` | زبان‌های مبدا و مقصد پشتیبانی‌شده. |
| `GET /api/health` | سلامت سرویس + اطلاعات منابع. |

### وضعیت‌های job (State Machine)

```
queued → downloading → extracting_audio → transcribing → translating
       → generating_voice → synchronizing → rendering → completed
                                                              ↘ failed
                                                              ↘ cancelled
```

### SSE Event Format

```
event: status
data: {"status":"transcribing","progress":25,"stage":"transcribing"}

event: status
data: {"status":"completed","progress":100,"stage":"completed"}

event: done
data: {"status":"completed"}
```

---

## پایپ‌لاین پردازش

مرحله به مرحله با ذخیره artifact در `storage/jobs/{job_id}/`:

| مرحله | artifact | توضیح |
|---|---|---|
| download | `input/video.mp4`, `input/metadata.json` | yt-dlp، ترجیح 720p برای CPU. |
| extract_audio | `audio/audio.wav` | 16kHz mono WAV مناسب Whisper. |
| transcribe | `transcript/transcript.json` | segments با `id`, `start`, `end`, `text` + detected language. |
| translate | `translation/translation.json` | ترجمه batched با حفظ ID. |
| generate_voice + synchronize | `tts/seg_*.wav`, `tts/stretched/seg_*.wav`, `tts/timing.json`, `audio/timeline_final.wav` | TTS + time-stretch + overlay. |
| render | `output/dubbed.mp4` | video stream copy + audio encode (سریع). |

---

## ماژولار بودن و تعویض موتورها

هر سرویس به یک Interface وابسته است، نه به پیاده‌سازی مشخص:

```python
# TTS — در app/services/tts/base.py
class TTSProvider(ABC):
    def available_voices(self) -> list[dict]: ...
    def default_voice(self, target_lang: str) -> str: ...
    def generate_audio(self, text, voice, output_path) -> float: ...
    def supports_lang(self, lang: str) -> bool: ...
```

برای افزودن مثلاً ElevenLabs یا Gemini TTS، فقط کلاس جدیدی بسازید که از `TTSProvider` ارث ببرد و در `registry.py` ثبتش کنید. بقیه‌ی برنامه بدون تغییر کار می‌کند.

همین الگو برای Whisper (transcription.py)، Gemini (translation.py)، YouTube (youtube.py) و FFmpeg (ffmpeg.py) اعمال می‌شود.

---

## هماهنگ‌سازی صدا (Sync)

هدف: صدای دوبله نباید timing ویدیوی اصلی را خراب کند.

الگوریتم (`app/utils/timing.py` — کاملاً تست‌شده):
1. برای هر segment، مدت clip تولیدشده توسط TTS را با ffprobe می‌سنجیم.
2. `speed = clip_duration / slot_duration` را محاسبه می‌کنیم.
3. اگر `speed ≤ SYNC_MAX_SPEED` (پیش‌فرض ۱.۳۰): clip دقیقاً در slot جا می‌گیرد (با atempo).
4. اگر `speed > max`: سرعت روی `max` clamp می‌شود و clip کمی طولانی‌تر از slot می‌شود (segment بعدی عقب می‌رود ولی هرگز قبل از start اصلی‌اش شروع نمی‌شود).
5. اگر `speed < min` (پیش‌فرض ۰.۸۰): clip با سرعت طبیعی پخش می‌شود و بقیه‌ی slot سکوت می‌ماند (طبیعی‌تر از کند کردن شدید).
6. clipهای stretch‌شده روی یک timeline بی‌صدا در زمان `start` خود overlay می‌شوند.

مثال واقعی از تست یکپارچه:
- clip 2.57s، slot 3.0s → speed 0.856 (کند → دقیقاً جا می‌شود)
- clip 3.34s، slot 3.0s → speed 1.112 (تند → دقیقاً جا می‌شود)
- clip 2.50s، slot 4.0s → speed 1.0 (طبیعی + سکوت)

---

## Resume / Recovery

اگر یک job در وسط یک مرحله (مثلاً TTS) شکست بخورد، با اجرای مجدد، فایل‌های artifact معتبر قبلی تشخیص داده می‌شوند و از همان مرحله ادامه می‌یابد:

- اگر `input/video.mp4` وجود داشت → دانلود دوباره نمی‌شود.
- اگر `audio/audio.wav` وجود داشت → استخراج صدا تکرار نمی‌شود.
- اگر `transcript/transcript.json` بود → Whisper دوباره اجرا نمی‌شود.
- اگر `translation/translation.json` بود → Gemini دوباره فراخوانی نمی‌شود.
- اگر `tts/seg_*.wav` برای یک segment بود → TTS برایش دوباره اجرا نمی‌شود.
- اگر `tts/timing.json` بود → کل مرحله sync رد می‌شود.
- اگر `output/dubbed.mp4` بود → render نهایی رد می‌شود.

به‌علاوه، اگر سرور در وسط اجرای یک job ری‌استارت شود، jobهای در حال اجرا به‌صورت خودکار دوباره در صف قرار می‌گیرند (`_reenqueue_transient` در `job_manager.py`).

---

## امنیت

- ✅ اعتبارسنجی سختگیرانه‌ی URL یوتیوب (`extract_video_id` + whitelist hostها).
- ✅ جلوگیری از Path Traversal: `job_id` فقط UUID معتبر می‌پذیرد؛ `is_safe_subpath` همه‌ی مسیرها را چک می‌کند.
- ✅ محدودیت حجم دانلود و مدت ویدیو.
- ✅ محدودیت job همزمان (`MAX_CONCURRENT_JOBS`).
- ✅ Timeout برای subprocessهای FFmpeg (۱۸۰۰ ثانیه).
- ✅ Sanitize filenameها (`sanitize_filename`).
- ✅ API Key هرگز در HTML، Git، log یا response قرار نمی‌گیرد. یک RedactingFormatter همه‌ی logها را فیلتر می‌کند.
- ✅ کلید واردشده از UI فقط در حافظه‌ی پردازش نگه داشته می‌شود (`.env` برای ماندگاری).
- ✅ استفاده از `.env` و `.env.example` (`.env` در `.gitignore` است).

---

## Docker

`backend/Dockerfile` یک image سبک Python 3.11 + FFmpeg می‌سازد. `docker-compose.yml` هم backend و هم frontend را orchestrate می‌کند:

```bash
export GEMINI_API_KEY="..."
docker compose up --build
# backend:   http://localhost:8000
# frontend:  http://localhost:3000
```

volume `./backend/storage` برای ماندگاری jobها و دیتابیس mount می‌شود.

---

## تست‌ها

تست‌های واحد (بدون نیاز به اینترنت یا کلید واقعی) برای بخش‌های بحرانی:

```bash
cd backend
pip install pytest pytest-asyncio   # اگر نصب نیست
PYTHONPATH=. python3 -m pytest tests/ -v
```

فایل‌های تست:
- `test_security.py` — اعتبارسنجی URL، Sanitize filename، path traversal، redact API key.
- `test_transcript.py` — (de)serialize متن و ترجمه.
- `test_translation.py` — parse پاسخ Gemini (با code fences، متن اضافی، JSON ناقص).
- `test_timing.py` — ریاضیات هماهنگ‌سازی (speed، clamp، overlap، timestamp).
- `test_tts.py` — interface و registry موتور TTS.
- `test_job_manager.py` — state machine و lifecycle job.
- `integration_pipeline.py` — تست یکپارچه‌ی واقعی TTS→sync→render (نیازمند یک ویدیوی دانلودشده).

تست Gemini و YouTube از Mock استفاده می‌کنند، ولی خود Application هیچ Mock Data یا Demo Mode ندارد.

---

## نکات منابع Codespaces

- این پروژه روی **CPU-only** کار می‌کند (فرض بر نبود GPU است).
- در Startup، منابع (CPU/RAM/GPU) بررسی می‌شود و با `WHISPER_MODEL=auto` مدل مناسب انتخاب می‌شود (`tiny` برای RAM کم، `base` برای ۳GB+، `small` برای ۸GB+).
- ویدیوها به‌صورت پیش‌فرض 720p دانلود می‌شوند تا CPU و RAM کمتر مصرف شود.
- در مرحله render نهایی، video stream **copy** می‌شود (نه re-encode) تا تقریباً آنی باشد.
- `MAX_CONCURRENT_JOBS=1` به‌صورت پیش‌فرض برای جلوگیری از OOM روی ۴GB RAM.

---

## نکات حقوقی

این ابزار برای دریافت و پردازش محتوایی طراحی شده که **شما مجاز به دانلود و پردازش آن هستید**. لطفاً حقوق صاحب محتوا، شرایط YouTube، و قوانین کپی‌رایت را رعایت کنید. این پروژه هیچ مکانیزمی برای دور زدن محدودیت‌های YouTube (age-gate، region-lock و غیره) ندارد و نباید چنین استفاده‌ای بکند.

---

ساخته‌شده با FastAPI + Next.js + faster-whisper + Google Gemini + edge-tts + FFmpeg.
