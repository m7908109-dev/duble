"""API route: TTS voice listing and provider info."""
from __future__ import annotations

from fastapi import APIRouter, HTTPException

from app.models.job import SettingsView  # noqa: F401
from app.services.tts import registry

router = APIRouter(prefix="/api/tts", tags=["tts"])


@router.get("/providers")
async def list_providers() -> dict:
    return {"providers": registry.list_providers()}


@router.get("/voices")
async def list_voices(provider: str | None = None, language: str | None = None) -> dict:
    voices = registry.all_voices(provider=provider)
    if language:
        lang = language.lower()
        voices = [v for v in voices if v.get("language", "").lower().startswith(lang)]
    return {"voices": voices}
