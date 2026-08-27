"""FastAPI application entry point.

Run with:  uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
"""
from __future__ import annotations

import contextlib
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from app.api.routes import jobs, settings as settings_route, tts, video
from app.core.config import settings
from app.core.logging import get_logger, setup_logging
from app.core.resources import detect_resources
from app.models import database
from app.services.tts import registry as tts_registry
from app.workers.job_manager import manager

log = get_logger(__name__)


@contextlib.asynccontextmanager
async def lifespan(app: FastAPI):
    setup_logging()
    log.info("Booting Automatic Video Dubbing Engine")
    res = detect_resources()
    log.info("Resources: %s", res.to_dict())
    if not res.ffmpeg_available:
        log.error("FFmpeg is not installed; video processing will fail.")
    if not res.yt_dlp_available:
        log.warning("yt-dlp not on PATH (using python package directly).")
    await database.init_db()
    tts_registry.ensure_registered()
    manager.start()
    log.info("Startup complete. Listening on %s:%d", settings.host, settings.port)
    yield
    log.info("Shutting down.")


app = FastAPI(
    title="Automatic Video Dubbing Engine",
    description="Open-source YouTube -> speech -> Gemini translation -> TTS -> dubbed video.",
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# --- Routes ---
app.include_router(video.router)
app.include_router(jobs.router)
app.include_router(settings_route.router)
app.include_router(tts.router)


@app.get("/api/health")
async def health() -> dict:
    res = detect_resources()
    return {
        "status": "ok",
        "resources": res.to_dict(),
        "whisper_model": settings.whisper_model,
        "tts_provider": settings.tts_provider,
        "has_gemini_key": settings.has_gemini_key,
    }


@app.get("/api/languages")
async def languages() -> dict:
    return {
        "source": [
            {"code": "auto", "name": "تشخیص خودکار"},
            {"code": "en", "name": "English"},
            {"code": "fa", "name": "فارسی"},
            {"code": "ar", "name": "العربية"},
            {"code": "tr", "name": "Türkçe"},
            {"code": "fr", "name": "Français"},
            {"code": "de", "name": "Deutsch"},
            {"code": "es", "name": "Español"},
            {"code": "ru", "name": "Русский"},
            {"code": "zh", "name": "中文"},
            {"code": "hi", "name": "हिन्दी"},
            {"code": "ur", "name": "اردو"},
            {"code": "az", "name": "Azərbaycan"},
            {"code": "ku", "name": "Kurdî"},
        ],
        "target": [
            {"code": "fa", "name": "فارسی"},
            {"code": "en", "name": "English"},
            {"code": "ar", "name": "العربية"},
            {"code": "tr", "name": "Türkçe"},
            {"code": "fr", "name": "Français"},
            {"code": "de", "name": "Deutsch"},
            {"code": "es", "name": "Español"},
            {"code": "ru", "name": "Русский"},
            {"code": "zh", "name": "中文"},
            {"code": "hi", "name": "हिन्दी"},
            {"code": "ur", "name": "اردو"},
            {"code": "az", "name": "Azərbaycan"},
            {"code": "ku", "name": "Kurdî"},
        ],
    }


# --- Serve built frontend (static) if present ---
_FRONTEND_DIR = Path(__file__).resolve().parent.parent / "frontend"
if _FRONTEND_DIR.is_dir():
    # Mount /app/* as static (the Next.js dev server serves the real UI).
    app.mount("/app", StaticFiles(directory=str(_FRONTEND_DIR), html=True), name="frontend")
