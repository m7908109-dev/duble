"""Tests for audio synchronization timing math."""
from app.utils.timing import (
    compute_speed,
    clamp_speed,
    build_sync_plans,
    has_overlap,
    format_timestamp,
)


def test_compute_speed_basic():
    # clip 3s, slot 2s -> need to speed up to 1.5x
    assert abs(compute_speed(3.0, 2.0) - 1.5) < 1e-6
    # clip 2s, slot 4s -> slow down to 0.5x
    assert abs(compute_speed(2.0, 4.0) - 0.5) < 1e-6


def test_compute_speed_zero_safe():
    assert compute_speed(0.0, 3.0) == 1.0
    assert compute_speed(3.0, 0.0) == 1.0


def test_clamp_speed():
    assert clamp_speed(1.0, 0.8, 1.3) == 1.0
    assert clamp_speed(2.0, 0.8, 1.3) == 1.3
    assert clamp_speed(0.5, 0.8, 1.3) == 0.8


def test_build_sync_plans_exact_fit():
    """When clip == slot, speed should be ~1.0."""
    segments = [
        {"id": 1, "start": 0.0, "end": 3.0},
        {"id": 2, "start": 3.0, "end": 6.0},
    ]
    durations = {1: 3.0, 2: 3.0}
    plans = build_sync_plans(segments, durations, min_speed=0.8, max_speed=1.3)
    assert len(plans) == 2
    assert abs(plans[0].speed - 1.0) < 1e-6
    assert abs(plans[0].final_duration - 3.0) < 1e-6
    assert plans[0].start == 0.0
    assert plans[1].start == 3.0


def test_build_sync_plans_speedup_clamped():
    """If clip is much longer than slot, speed clamps to max and clip overruns."""
    segments = [{"id": 1, "start": 0.0, "end": 2.0}]  # 2s slot
    durations = {1: 10.0}  # 10s clip
    plans = build_sync_plans(segments, durations, min_speed=0.8, max_speed=1.3)
    assert plans[0].speed == 1.3
    assert abs(plans[0].final_duration - 10.0 / 1.3) < 1e-6


def test_build_sync_plans_short_clip_keeps_natural_speed():
    """If clip is much shorter than slot, we don't slow it down too much —
    it plays at natural speed and leaves silence."""
    segments = [{"id": 1, "start": 0.0, "end": 10.0}]  # 10s slot
    durations = {1: 2.0}  # 2s clip
    plans = build_sync_plans(segments, durations, min_speed=0.8, max_speed=1.3)
    assert plans[0].speed == 1.0
    assert abs(plans[0].final_duration - 2.0) < 1e-6


def test_build_sync_plans_no_overlap():
    """Successive clips must not overlap in the produced timeline."""
    segments = [
        {"id": 1, "start": 0.0, "end": 3.0},
        {"id": 2, "start": 3.0, "end": 6.0},
        {"id": 3, "start": 6.0, "end": 9.0},
    ]
    durations = {1: 3.0, 2: 4.0, 3: 2.0}
    plans = build_sync_plans(segments, durations, min_speed=0.8, max_speed=1.3)
    assert not has_overlap(plans)


def test_format_timestamp():
    assert format_timestamp(0) == "00:00:00"
    assert format_timestamp(12.42) == "00:00:12"
    assert format_timestamp(3725) == "01:02:05"
    assert format_timestamp(-5) == "00:00:00"
    assert format_timestamp(float("inf")) == "00:00:00"
