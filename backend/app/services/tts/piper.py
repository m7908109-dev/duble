"""Piper TTS provider — truly local/offline neural TTS.

Piper (https://github.com/rhasspy/piper) ships ONNX voices that run
comfortably on CPU. To use it you must:
  1. Install the piper-tts python package OR download the piper binary.
  2. Download a voice model (.onnx + .onnx.json) for your target language
     from https://huggingface.co/rhasspy/piper-voices
  3. Set PIPER_MODEL_PATH / PIPER_CONFIG_PATH in .env (or pass via UI).

This adapter calls the `piper` CLI if present, otherwise tries the
piper-tts python package. Voices are listed from the configured model only
(piper has no central voice index in-process).
"""
from __future__ import annotations

import os
import shutil
import subprocess
from pathlib import Path
from typing import Dict, List

from app.core.config import settings
from app.core.logging import get_logger
from app.services.ffmpeg import probe_duration
from app.services.tts.base import TTSProvider

log = get_logger(__name__)


class PiperTTSProvider(TTSProvider):
    name = "piper"

    def _model_path(self) -> str | None:
        return settings.piper_model_path or None

    def _binary(self) -> str | None:
        return shutil.which("piper")

    def available_voices(self) -> List[Dict[str, str]]:
        model = self._model_path()
        if not model or not Path(model).exists():
            return []
        name = Path(model).stem
        return [
            {
                "id": name,
                "name": f"Piper voice: {name}",
                "language": "configured",
                "gender": "",
            }
        ]

    def default_voice(self, target_lang: str) -> str:
        voices = self.available_voices()
        return voices[0]["id"] if voices else "piper-default"

    def supports_lang(self, lang: str) -> bool:
        # We cannot enumerate all piper voices; assume yes if a model is set.
        return bool(self._model_path())

    def generate_audio(self, text: str, voice: str, output_path: str) -> float:
        model = self._model_path()
        if not model:
            raise RuntimeError(
                "Piper model path not configured. Set PIPER_MODEL_PATH."
            )
        os.makedirs(os.path.dirname(output_path) or ".", exist_ok=True)
        if Path(output_path).exists():
            Path(output_path).unlink()
        binary = self._binary()
        if binary:
            cmd = [
                binary,
                "-m",
                model,
                "-f",
                output_path,
                "--output-raw",
            ]
            log.debug("piper cmd: %s", cmd)
            proc = subprocess.run(
                cmd,
                input=text.encode("utf-8"),
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                timeout=120,
                check=False,
            )
            if proc.returncode != 0:
                raise RuntimeError(
                    f"piper failed: {proc.stderr.decode('utf-8','ignore')[-1000:]}"
                )
            # Convert raw to wav.
            wav_path = str(Path(output_path).with_suffix(".wav"))
            self._raw_to_wav(output_path, wav_path, sample_rate=22050)
            if Path(output_path).exists() and output_path != wav_path:
                Path(output_path).unlink()
            final = wav_path
        else:
            # Try the piper_tts python package.
            try:
                from piper.voice import PiperVoice  # type: ignore
            except Exception as exc:
                raise RuntimeError(
                    "Neither piper binary nor piper-tts python package available."
                ) from exc
            voice_obj = PiperVoice.load(model)
            wav_path = output_path if output_path.endswith(".wav") else str(
                Path(output_path).with_suffix(".wav")
            )
            with open(wav_path, "wb") as fh:
                voice_obj.synthesize(text, fh)
            final = wav_path

        duration = probe_duration(final) if Path(final).exists() else 0.0
        # Normalize final path to output_path if different (caller expects it).
        if final != output_path:
            shutil.move(final, output_path)
        return float(duration or 0.0)

    def _raw_to_wav(self, raw_path: str, wav_path: str, sample_rate: int) -> None:
        import wave

        with wave.open(wav_path, "wb") as w:
            w.setnchannels(1)
            w.setsampwidth(2)
            w.setframerate(sample_rate)
            with open(raw_path, "rb") as fh:
                w.writeframes(fh.read())
