"""edge-tts provider.

edge-tts is a free Python library that wraps Microsoft Edge's online TTS.
It is reliable on Codespaces (needs internet), supports many languages
including Persian (fa-IR), and requires NO model downloads.

NOTE: it is "free" but technically fetches audio from a remote service,
not a fully local engine. For a fully-offline engine, use the `piper`
provider. The adapter pattern lets you switch without touching the backend.
"""
from __future__ import annotations

import asyncio
from typing import Dict, List

from app.core.logging import get_logger
from app.services.ffmpeg import probe_duration
from app.services.tts.base import TTSProvider

log = get_logger(__name__)


class EdgeTTSProvider(TTSProvider):
    name = "edge"

    # A curated subset covering the languages offered in the UI.
    _VOICES_CACHE: List[Dict[str, str]] | None = None

    def available_voices(self) -> List[Dict[str, str]]:
        if self._VOICES_CACHE is not None:
            return self._VOICES_CACHE
        import threading

        result_holder: dict = {}

        def _worker() -> None:
            try:
                import edge_tts  # type: ignore

                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
                try:
                    voices = loop.run_until_complete(edge_tts.list_voices())
                    result_holder["voices"] = voices
                finally:
                    loop.close()
            except Exception as exc:  # pragma: no cover
                result_holder["error"] = exc

        t = threading.Thread(target=_worker, daemon=True)
        t.start()
        t.join(timeout=30)
        if "error" in result_holder:
            log.warning("Could not list edge-tts voices: %s", result_holder["error"])
            self._VOICES_CACHE = []
            return self._VOICES_CACHE
        if t.is_alive():
            log.warning("edge-tts list_voices timed out (>30s)")
            self._VOICES_CACHE = []
            return self._VOICES_CACHE
        voices = result_holder.get("voices", [])
        out: List[Dict[str, str]] = []
        for v in voices:
            out.append(
                {
                    "id": v.get("ShortName", ""),
                    "name": v.get("FriendlyName") or v.get("ShortName", ""),
                    "language": v.get("Locale", ""),
                    "gender": v.get("Gender", ""),
                }
            )
        self._VOICES_CACHE = out
        return out

    def default_voice(self, target_lang: str) -> str:
        voices = self.available_voices()
        # target_lang like 'fa' -> locale prefix 'fa-'
        prefix = target_lang.lower() + "-"
        # Prefer a female neural voice for the language.
        for v in voices:
            if v["language"].lower().startswith(prefix) and "Female" in v["gender"]:
                return v["id"]
        for v in voices:
            if v["language"].lower().startswith(prefix):
                return v["id"]
        # Fallback to a Persian voice if nothing matched.
        for v in voices:
            if v["language"].lower().startswith("fa-"):
                return v["id"]
        return "fa-IR-GhazalNeural"

    def generate_audio(self, text: str, voice: str, output_path: str) -> float:
        import os
        import threading

        os.makedirs(os.path.dirname(output_path) or ".", exist_ok=True)
        try:
            import edge_tts  # type: ignore
        except Exception as exc:
            raise RuntimeError(f"edge-tts not installed: {exc}") from exc

        # edge-tts is async; we may be running inside an existing event loop,
        # so run the coroutine in a dedicated thread with its own loop.
        result_holder: dict = {}

        def _worker() -> None:
            try:
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
                try:
                    communicate = edge_tts.Communicate(text=text, voice=voice)
                    loop.run_until_complete(communicate.save(output_path))
                finally:
                    loop.close()
            except Exception as exc:  # pragma: no cover
                result_holder["error"] = exc

        t = threading.Thread(target=_worker, daemon=True)
        t.start()
        t.join(timeout=120)
        if "error" in result_holder:
            raise RuntimeError(f"edge-tts synthesis failed: {result_holder['error']}")
        if t.is_alive():
            raise RuntimeError("edge-tts synthesis timed out (>120s)")
        if not os.path.exists(output_path) or os.path.getsize(output_path) == 0:
            raise RuntimeError("edge-tts produced no audio output")
        duration = probe_duration(output_path)
        return float(duration or 0.0)

    def supports_lang(self, lang: str) -> bool:
        voices = self.available_voices()
        prefix = lang.lower() + "-"
        return any(v["language"].lower().startswith(prefix) for v in voices)
