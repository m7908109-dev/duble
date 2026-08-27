"""TTS provider interface + registry.

To swap TTS engines, implement `TTSProvider` and register it in
`tts.registry`. The rest of the application (job_manager, dubbing) only
depends on this interface — never on a concrete provider.

Providers shipped:
  - edge    : edge-tts (free, reliable; uses Microsoft Edge online service)
  - piper   : piper-tts (truly local/offline; requires model files)
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Dict, List


class TTSProvider(ABC):
    """Abstract TTS provider.

    Implementations must be safe to construct cheaply; heavy resources
    (model weights) should be loaded lazily on first generate_audio() call.
    """

    name: str = "base"

    @abstractmethod
    def available_voices(self) -> List[Dict[str, str]]:
        """Return a list of voice descriptors: {id, name, language, gender}."""

    @abstractmethod
    def default_voice(self, target_lang: str) -> str:
        """Return a sensible default voice id for a language code."""

    @abstractmethod
    def generate_audio(
        self,
        text: str,
        voice: str,
        output_path: str,
    ) -> float:
        """Synthesize speech for `text` with `voice` into `output_path`.

        Returns the audio duration in seconds.
        """

    @abstractmethod
    def supports_lang(self, lang: str) -> bool:
        """Whether this provider can synthesize the given language."""


_REGISTRY: Dict[str, TTSProvider] = {}


def register(provider: TTSProvider) -> None:
    _REGISTRY[provider.name] = provider


def get_provider(name: str) -> TTSProvider:
    if name not in _REGISTRY:
        raise ValueError(
            f"Unknown TTS provider '{name}'. Registered: {list(_REGISTRY)}"
        )
    return _REGISTRY[name]


def list_providers() -> List[str]:
    return list(_REGISTRY.keys())


def all_voices(provider: str | None = None) -> List[Dict[str, str]]:
    if provider:
        return get_provider(provider).available_voices()
    out: List[Dict[str, str]] = []
    for name, prov in _REGISTRY.items():
        for v in prov.available_voices():
            v = dict(v)
            v.setdefault("provider", name)
            out.append(v)
    return out
