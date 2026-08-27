"""Speech-to-Text service using faster-whisper (CTranslate2 backend, CPU-friendly).

The model is loaded lazily and cached for the process lifetime. On first
use, the model is downloaded from HuggingFace to the HF cache directory.
"""
from __future__ import annotations

import json
from typing import List, Optional

from app.core.config import settings
from app.core.logging import get_logger
from app.core.resources import detect_resources, recommended_whisper_model
from app.models.job import Segment, Transcript
from app.services import ffmpeg

log = get_logger(__name__)

# Module-level lazy model cache.
_MODEL = None
_MODEL_KEY = None


def _resolve_device() -> str:
    dev = settings.whisper_device
    if dev == "auto":
        res = detect_resources()
        return "cuda" if res.has_cuda else "cpu"
    return dev


def _resolve_model() -> str:
    return recommended_whisper_model(detect_resources(), settings.whisper_model)


def _get_model():
    global _MODEL, _MODEL_KEY
    model_name = _resolve_model()
    device = _resolve_device()
    compute = settings.whisper_compute_type
    key = (model_name, device, compute)
    if _MODEL is not None and _MODEL_KEY == key:
        return _MODEL
    log.info(
        "Loading faster-whisper model='%s' device='%s' compute='%s'",
        model_name,
        device,
        compute,
    )
    from faster_whisper import WhisperModel  # type: ignore

    _MODEL = WhisperModel(
        model_name,
        device=device,
        compute_type=compute,
    )
    _MODEL_KEY = key
    return _MODEL


def transcribe(
    audio_path,
    source_lang: Optional[str] = None,
    beam_size: Optional[int] = None,
) -> Transcript:
    """Transcribe an audio file and return a Transcript with timestamps."""
    from pathlib import Path

    audio = Path(audio_path)
    if not audio.exists():
        raise FileNotFoundError(f"Audio file not found: {audio}")

    model = _get_model()
    lang_arg = source_lang if source_lang and source_lang != "auto" else None
    bs = beam_size or settings.whisper_beam_size
    log.info("Transcribing %s (lang=%s, beam=%s)", audio, lang_arg, bs)

    segments_iter, info = model.transcribe(
        str(audio),
        language=lang_arg,
        beam_size=bs,
        vad_filter=True,
        vad_parameters={"min_silence_duration_ms": 500},
    )

    segments: List[Segment] = []
    for idx, seg in enumerate(segments_iter):
        text = (seg.text or "").strip()
        if not text:
            continue
        segments.append(
            Segment(
                id=idx + 1,
                start=float(seg.start),
                end=float(seg.end),
                text=text,
            )
        )

    detected = getattr(info, "language", None)
    duration = getattr(info, "duration", float(audio.duration if audio.exists() else 0.0)) or None
    transcript = Transcript(
        language=detected,
        duration=duration,
        segments=segments,
    )
    log.info(
        "Transcription done: %d segments, language=%s, duration=%s",
        len(segments),
        detected,
        duration,
    )
    return transcript


def save_transcript(transcript: Transcript, dest_path) -> None:
    from pathlib import Path

    p = Path(dest_path)
    p.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "language": transcript.language,
        "duration": transcript.duration,
        "segments": [s.model_dump() for s in transcript.segments],
    }
    p.write_text(json.dumps(payload, ensure_ascii=False, indent=2), "utf-8")


def load_transcript(src_path) -> Transcript:
    from pathlib import Path

    p = Path(src_path)
    if not p.exists():
        raise FileNotFoundError(f"Transcript file not found: {p}")
    data = json.loads(p.read_text("utf-8"))
    return Transcript(**data)
