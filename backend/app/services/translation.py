"""Translation service using Google Gemini.

Design:
  - Transcript is split into BATCHES (by segment count and token budget).
  - Each batch is sent to Gemini with a strict JSON contract.
  - The model must return ONLY a JSON array mirroring the input IDs.
  - Output is parsed defensively (strip code fences, JSON repair fallback).

We NEVER log or return the API key.
"""
from __future__ import annotations

import json
import re
from typing import List

from app.core.config import settings
from app.core.logging import get_logger
from app.models.job import Transcript, Translation, TranslatedSegment

log = get_logger(__name__)

# Batch size: 50 segments per request (also bounded by token estimate).
BATCH_SIZE = 50


class TranslationError(RuntimeError):
    pass


_LANGUAGE_NAMES = {
    "fa": "Persian",
    "en": "English",
    "ar": "Arabic",
    "tr": "Turkish",
    "fr": "French",
    "de": "German",
    "es": "Spanish",
    "ru": "Russian",
    "zh": "Chinese",
    "hi": "Hindi",
    "ur": "Urdu",
    "az": "Azerbaijani",
    "ku": "Kurdish",
}


def _lang_name(code: str) -> str:
    return _LANGUAGE_NAMES.get(code, code)


def _build_prompt(batch: List[dict], source: str, target: str) -> str:
    src_name = _lang_name(source) if source and source != "auto" else "the source language"
    tgt_name = _lang_name(target)
    return (
        "You are a professional video-dubbing translator. "
        f"Translate each segment's `text` from {src_name} to {tgt_name}.\n"
        "Rules:\n"
        "1. Output ONLY a JSON array. No markdown fences, no commentary.\n"
        "2. Each element MUST have `id` and `translation` keys only.\n"
        "3. Preserve the original `id` of every segment in order.\n"
        "4. Translate naturally and idiomatically, keeping context flow.\n"
        "5. Keep translations concise enough to be spoken aloud.\n"
        "6. Do NOT add, drop, or reorder segments.\n\n"
        "Input segments (JSON):\n"
        f"{json.dumps(batch, ensure_ascii=False)}\n\n"
        "Return the JSON array now."
    )


def _strip_fences(text: str) -> str:
    text = text.strip()
    # Remove ```json ... ``` fences if present.
    fence = re.match(r"^```(?:json)?\s*(.*?)\s*```$", text, re.DOTALL)
    if fence:
        return fence.group(1).strip()
    return text


def _parse_response(raw: str, expected_ids: List[int]) -> List[dict]:
    """Parse Gemini's response into a list of {id, translation} dicts.

    We try strict JSON first, then a permissive regex fallback.
    """
    cleaned = _strip_fences(raw)
    try:
        data = json.loads(cleaned)
    except json.JSONDecodeError:
        # Fallback: find the first '[' ... matching ']' substring.
        match = re.search(r"\[.*\]", cleaned, re.DOTALL)
        if not match:
            raise TranslationError("Gemini response is not valid JSON")
        try:
            data = json.loads(match.group(0))
        except json.JSONDecodeError as exc:
            raise TranslationError(f"Could not parse JSON: {exc}") from exc
    if not isinstance(data, list):
        raise TranslationError("Gemini response is not a JSON array")
    out = []
    for item in data:
        if not isinstance(item, dict):
            continue
        iid = item.get("id")
        tr = item.get("translation") or item.get("text") or ""
        if iid is None:
            continue
        try:
            iid = int(iid)
        except (TypeError, ValueError):
            continue
        out.append({"id": iid, "translation": str(tr).strip()})
    if len(out) != len(expected_ids):
        log.warning(
            "Gemini returned %d items, expected %d", len(out), len(expected_ids)
        )
    return out


def _client():
    """Build a Gemini client. Requires a configured API key."""
    if not settings.has_gemini_key:
        raise TranslationError(
            "GEMINI_API_KEY is not set. Add it to .env or via the Settings UI."
        )
    from google import genai  # type: ignore

    return genai.Client(api_key=settings.gemini_api_key)


def translate(
    transcript: Transcript, target_lang: str
) -> Translation:
    """Translate an entire transcript in batches, preserving segment IDs."""
    if not transcript.segments:
        return Translation(source_language=transcript.language, target_language=target_lang)

    client = _client()
    segs = transcript.segments
    translated: List[TranslatedSegment] = []
    total_batches = (len(segs) + BATCH_SIZE - 1) // BATCH_SIZE
    log.info(
        "Translating %d segments in %d batch(es) to %s",
        len(segs),
        total_batches,
        target_lang,
    )
    for b_idx in range(total_batches):
        chunk = segs[b_idx * BATCH_SIZE : (b_idx + 1) * BATCH_SIZE]
        batch_payload = [{"id": s.id, "text": s.text} for s in chunk]
        prompt = _build_prompt(batch_payload, transcript.language or "auto", target_lang)
        try:
            resp = client.models.generate_content(
                model=settings.gemini_model,
                contents=prompt,
            )
            raw = getattr(resp, "text", "") or ""
        except Exception as exc:
            raise TranslationError(f"Gemini request failed (batch {b_idx + 1}): {exc}") from exc
        parsed = _parse_response(raw, [s.id for s in chunk])
        by_id = {p["id"]: p["translation"] for p in parsed}
        for s in chunk:
            translated.append(
                TranslatedSegment(
                    id=s.id,
                    start=s.start,
                    end=s.end,
                    text=s.text,
                    translation=by_id.get(s.id, s.text) or s.text,
                )
            )
        log.info("Batch %d/%d translated", b_idx + 1, total_batches)
    return Translation(
        source_language=transcript.language,
        target_language=target_lang,
        segments=translated,
    )


def save_translation(translation: Translation, dest_path) -> None:
    from pathlib import Path

    p = Path(dest_path)
    p.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "source_language": translation.source_language,
        "target_language": translation.target_language,
        "segments": [s.model_dump() for s in translation.segments],
    }
    p.write_text(json.dumps(payload, ensure_ascii=False, indent=2), "utf-8")


def load_translation(src_path) -> Translation:
    from pathlib import Path

    p = Path(src_path)
    if not p.exists():
        raise FileNotFoundError(f"Translation file not found: {p}")
    data = json.loads(p.read_text("utf-8"))
    return Translation(**data)
