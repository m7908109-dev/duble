"""API route: runtime settings (Gemini key, TTS voice list, resources).

The Gemini API key entered via the UI is held in process memory only — we
do NOT persist it to disk. For a permanent key, the user should set
GEMINI_API_KEY in .env.
"""
from __future__ import annotations

import os

from fastapi import APIRouter, HTTPException

from app.core.config import settings
from app.core.logging import get_logger
from app.core.resources import detect_resources
from app.models.job import SettingsUpdate, SettingsView
from app.services.tts import registry

log = get_logger(__name__)

router = APIRouter(prefix="/api/settings", tags=["settings"])


@router.get("", response_model=SettingsView)
async def get_settings_view() -> SettingsView:
    voices = registry.all_voices(provider=settings.tts_provider if settings.tts_provider else None)
    if not voices:
        # Fallback: try listing all providers' voices.
        voices = registry.all_voices()
    res = detect_resources().to_dict()
    return SettingsView(
        has_gemini_key=settings.has_gemini_key,
        whisper_model=settings.whisper_model,
        tts_provider=settings.tts_provider,
        tts_default_voice=settings.tts_default_voice,
        available_voices=voices,
        resources=res,
    )


@router.put("")
async def update_settings(payload: SettingsUpdate) -> dict:
    key = (payload.gemini_api_key or "").strip()
    if key:
        # Set on the process environment + on the singleton.
        os.environ["GEMINI_API_KEY"] = key
        # Mutate the cached singleton (pydantic Settings is mutable by default).
        settings.gemini_api_key = key
        log.info("Gemini API key updated via UI (length=%d)", len(key))
    return {"ok": True, "has_gemini_key": settings.has_gemini_key}
