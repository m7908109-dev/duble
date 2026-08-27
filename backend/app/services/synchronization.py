"""Audio synchronization: align TTS clips to original segment timing.

Pipeline:
  1. For each translated segment, the TTS provider generates a clip.
  2. We measure each clip's duration.
  3. We compute a per-clip speed factor (within safe limits) so clips
     fit their original time slot; clips that would need extreme stretching
     are clamped and allowed to slightly overrun.
  4. Each (possibly stretched) clip is overlaid onto a silent timeline
     at its start time, producing a single mixed dub track.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Dict, List

from app.core.config import settings
from app.core.logging import get_logger
from app.services import ffmpeg
from app.services.tts import registry as tts_registry
from app.services.ffmpeg import FFmpegError
from app.utils.paths import JobPaths
from app.utils.timing import SyncPlan, build_sync_plans, clamp_speed

log = get_logger(__name__)


class SyncError(RuntimeError):
    pass


def generate_clips(
    translation,  # Translation pydantic model
    provider: str,
    voice: str,
    paths: JobPaths,
) -> Dict[int, Path]:
    """Run TTS for every segment, return {segment_id: clip_path}."""
    provider_obj = tts_registry.get(provider)
    clips: Dict[int, Path] = {}
    for seg in translation.segments:
        text = (seg.translation or seg.text or "").strip()
        if not text:
            continue
        clip_path = paths.tts / f"seg_{seg.id:05d}.wav"
        if clip_path.exists() and clip_path.stat().st_size > 0:
            # Resume support: reuse already-generated clips.
            clips[seg.id] = clip_path
            continue
        try:
            provider_obj.generate_audio(text, voice, str(clip_path))
        except Exception as exc:
            raise SyncError(f"TTS failed for segment {seg.id}: {exc}") from exc
        if not clip_path.exists() or clip_path.stat().st_size == 0:
            raise SyncError(f"TTS produced no audio for segment {seg.id}")
        clips[seg.id] = clip_path
    return clips


def measure_durations(clips: Dict[int, Path]) -> Dict[int, float]:
    durations: Dict[int, float] = {}
    for sid, path in clips.items():
        dur = ffmpeg.probe_duration(path)
        if dur <= 0:
            dur = 0.0
        durations[sid] = dur
    return durations


def stretch_clips(
    clips: Dict[int, Path],
    plans: List[SyncPlan],
    paths: JobPaths,
) -> Dict[int, Path]:
    """Time-stretch each clip per its SyncPlan, returning the stretched paths."""
    out: Dict[int, Path] = {}
    stretched_dir = paths.tts / "stretched"
    stretched_dir.mkdir(parents=True, exist_ok=True)
    for plan in plans:
        clip = clips.get(plan.segment_id)
        if not clip:
            continue
        target = stretched_dir / f"seg_{plan.segment_id:05d}.wav"
        # If speed ~1.0 within tolerance, just copy.
        if abs(plan.speed - 1.0) < 0.01:
            target.write_bytes(clip.read_bytes())
        else:
            try:
                ffmpeg.stretch_clip(clip, target, plan.speed)
            except FFmpegError as exc:
                raise SyncError(f"stretch failed for {plan.segment_id}: {exc}") from exc
        out[plan.segment_id] = target
    return out


def compose_timeline(
    stretched: Dict[int, Path],
    plans: List[SyncPlan],
    total_duration: float,
    paths: JobPaths,
) -> Path:
    """Overlay all stretched clips onto a silent timeline of total_duration."""
    if total_duration <= 0:
        total_duration = max((p.start + p.final_duration for p in plans), default=1.0)
    base = paths.audio / "timeline_base.wav"
    ffmpeg.build_silent_track(total_duration, base, sample_rate=24000)

    current = base
    # Overlay incrementally into a rolling file to keep ffmpeg memory bounded.
    for idx, plan in enumerate(sorted(plans, key=lambda p: p.start)):
        clip = stretched.get(plan.segment_id)
        if not clip:
            continue
        nxt = paths.audio / f"timeline_{idx:05d}.wav"
        try:
            ffmpeg.overlay_clip_at(current, clip, plan.start, nxt)
        except FFmpegError as exc:
            raise SyncError(f"overlay failed for {plan.segment_id}: {exc}") from exc
        current = nxt
        # Clean up intermediate base (keep the latest).
        if current != base and base.exists():
            try:
                base.unlink()
            except Exception:
                pass
        base = nxt

    final = paths.audio / "timeline_final.wav"
    if current != final:
        # Move/copy the last rolling file to final name.
        final.write_bytes(current.read_bytes())
        # remove rolling intermediate
        try:
            current.unlink()
        except Exception:
            pass
    else:
        # If no clips were laid down, base IS the silent track — copy to final.
        final.write_bytes(base.read_bytes())
    return final


def save_sync_data(
    plans: List[SyncPlan],
    clips: Dict[int, Path],
    durations: Dict[int, float],
    path: Path,
) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "plans": [
            {
                "segment_id": p.segment_id,
                "start": p.start,
                "slot_end": p.slot_end,
                "clip_duration": p.clip_duration,
                "speed": p.speed,
                "final_duration": p.final_duration,
            }
            for p in plans
        ],
        "durations": durations,
        "clip_count": len(clips),
    }
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), "utf-8")


def synchronize(
    translation,
    provider: str,
    voice: str,
    paths: JobPaths,
    total_duration: float,
) -> Path:
    """Run the full sync pipeline; returns the final mixed dub track path."""
    clips = generate_clips(translation, provider, voice, paths)
    if not clips:
        # Nothing to dub — produce a silent track.
        final = paths.audio / "timeline_final.wav"
        ffmpeg.build_silent_track(max(total_duration, 1.0), final, sample_rate=24000)
        return final
    durations = measure_durations(clips)
    seg_dicts = [
        {"id": s.id, "start": s.start, "end": s.end} for s in translation.segments
    ]
    plans = build_sync_plans(
        seg_dicts,
        durations,
        settings.sync_min_speed,
        settings.sync_max_speed,
    )
    stretched = stretch_clips(clips, plans, paths)
    final = compose_timeline(stretched, plans, total_duration, paths)
    save_sync_data(plans, clips, durations, paths.timing_path)
    return final
