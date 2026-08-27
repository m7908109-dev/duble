"""Timing / synchronization math.

These functions are pure and unit-tested. They compute the optimal speed
factor for time-stretching a TTS clip to fit a slot, and the layout of
segments on the final dub timeline.
"""
from __future__ import annotations

import math
from dataclasses import dataclass
from typing import List


@dataclass
class SyncPlan:
    """How to place one TTS clip on the dub timeline."""

    segment_id: int
    # Where the clip should start in the final audio (seconds).
    start: float
    # The slot's end (seconds) — original segment end.
    slot_end: float
    # The clip's natural duration (seconds).
    clip_duration: float
    # Speed factor to apply so the clip fits (1.0 = no stretch).
    speed: float
    # Final duration after stretch (= clip_duration / speed).
    final_duration: float
    # Gain to apply.
    gain: float = 1.0


def clamp_speed(speed: float, min_speed: float, max_speed: float) -> float:
    if speed < min_speed:
        return min_speed
    if speed > max_speed:
        return max_speed
    return speed


def compute_speed(clip_duration: float, slot_duration: float) -> float:
    """Compute the speed factor so the clip fits exactly in the slot.

    Returns >1.0 to speed up (shorten), <1.0 to slow down (lengthen).
    """
    if clip_duration <= 0:
        return 1.0
    if slot_duration <= 0:
        return 1.0
    return clip_duration / slot_duration


def build_sync_plans(
    segments: List[dict],
    clip_durations: dict,
    min_speed: float,
    max_speed: float,
) -> List[SyncPlan]:
    """Lay out TTS clips on the timeline.

    Strategy (segment-by-segment, ordered):
      - The clip should START at the original segment's start, unless the
        previous clip overran its slot (then start right after it).
      - The available slot end is the original segment's end.
      - Compute the natural speed = clip_duration / slot_duration.
      - If natural speed <= max_speed, fit it exactly.
      - If it would need to go faster than max_speed, clamp to max_speed and
        let the clip run a little past the slot end (the next segment will be
        pushed back, but never before its original start).
    """
    plans: List[SyncPlan] = []
    cursor = 0.0  # earliest free time on the timeline
    for seg in sorted(segments, key=lambda s: s["start"]):
        seg_id = seg["id"]
        start = float(seg["start"])
        end = float(seg["end"])
        dur = float(clip_durations.get(seg_id, 0.0))
        # Don't let clips overlap a previous clip.
        start = max(start, cursor)
        slot_duration = max(0.0, end - start)
        speed = compute_speed(dur, slot_duration)
        if speed > max_speed:
            # Clamp: clip will be (dur / max_speed) long and overrun.
            speed = max_speed
        elif speed < min_speed and dur > 0:
            # Clip is shorter than slot; we DON'T slow it down too much —
            # keeping it at natural speed and adding silence is more natural.
            speed = 1.0
        final_duration = (dur / speed) if dur > 0 and speed > 0 else 0.0
        plans.append(
            SyncPlan(
                segment_id=seg_id,
                start=start,
                slot_end=end,
                clip_duration=dur,
                speed=speed,
                final_duration=final_duration,
            )
        )
        cursor = max(cursor, start + final_duration)
    return plans


def has_overlap(plans: List[SyncPlan]) -> bool:
    """Return True if any two clips overlap (sanity check)."""
    ordered = sorted(plans, key=lambda p: p.start)
    for prev, cur in zip(ordered, ordered[1:]):
        if cur.start < prev.start + prev.final_duration - 1e-6:
            return True
    return False


def format_timestamp(seconds: float) -> str:
    """00:00:12 style."""
    if not math.isfinite(seconds) or seconds < 0:
        seconds = 0.0
    total = int(seconds)
    h = total // 3600
    m = (total % 3600) // 60
    s = total % 60
    return f"{h:02d}:{m:02d}:{s:02d}"
