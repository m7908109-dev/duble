"""TTS provider registry.

Importing this module registers all shipped providers. The rest of the
app calls `registry.get(name)` and `registry.all_voices(provider=None)`.
"""
from __future__ import annotations

from typing import Dict, List, Optional

from app.services.tts.base import (
    TTSProvider,
    register as _register,
    get_provider as _get_provider,
    list_providers as _list_providers,
    all_voices as _all_voices,
)
from app.services.tts.edge import EdgeTTSProvider
from app.services.tts.piper import PiperTTSProvider

_REGISTERED = False


def ensure_registered() -> None:
    global _REGISTERED
    if _REGISTERED:
        return
    _register(EdgeTTSProvider())
    _register(PiperTTSProvider())
    _REGISTERED = True


def get(name: str) -> TTSProvider:
    ensure_registered()
    return _get_provider(name)


def list_providers() -> List[str]:
    ensure_registered()
    return _list_providers()


def all_voices(provider: Optional[str] = None) -> List[Dict[str, str]]:
    ensure_registered()
    return _all_voices(provider)
