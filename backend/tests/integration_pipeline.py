"""Integration test for the TTS -> synchronization -> render pipeline.

Uses the video.mp4 already downloaded by a real job run and exercises the
real TTS provider, the real sync/timing logic, and the real ffmpeg mux —
with a hand-crafted transcript + translation so we don't depend on Whisper
(which needs HuggingFace) or Gemini (which needs a real key).

Run from backend/:  python3 tests/integration_pipeline.py
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

# Ensure app is importable.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.core.logging import setup_logging, get_logger
from app.models.job import Transcript, Translation, TranslatedSegment, Segment
from app.services import ffmpeg, synchronization
from app.services.tts import registry
from app.utils.paths import JobPaths

setup_logging("INFO")
log = get_logger(__name__)


def main() -> int:
    # Find a job that already downloaded video.mp4.
    jobs_root = Path(__file__).resolve().parent.parent / "storage" / "jobs"
    if not jobs_root.exists():
        log.error("No jobs directory found; run a real job first to download a video.")
        return 1
    target_job = None
    for d in sorted(jobs_root.iterdir(), reverse=True):
        v = d / "input" / "video.mp4"
        if v.exists():
            target_job = d.name
            break
    if not target_job:
        log.error("No job with a downloaded video.mp4 found.")
        return 1

    log.info("Using job %s for integration test", target_job)
    paths = JobPaths(target_job).ensure()

    # Make sure the source audio exists; if not, extract it.
    if not paths.audio_path.exists():
        log.info("Extracting audio from video...")
        ffmpeg.extract_audio(paths.video_path, paths.audio_path)
    log.info("Audio at %s", paths.audio_path)

    # Probe video duration.
    dur = ffmpeg.probe_duration(paths.video_path)
    log.info("Video duration: %.2fs", dur)

    # Build a synthetic transcript + translation with 3 short Persian segments
    # placed at safe timestamps inside the first 30 seconds.
    transcript = Transcript(
        language="en",
        duration=dur,
        segments=[
            Segment(id=1, start=1.0, end=4.0, text="Hello everyone, welcome back."),
            Segment(id=2, start=5.0, end=8.0, text="Today we will talk about something interesting."),
            Segment(id=3, start=10.0, end=14.0, text="Let's get started right away."),
        ],
    )
    translation = Translation(
        source_language="en",
        target_language="fa",
        segments=[
            TranslatedSegment(id=1, start=1.0, end=4.0, text="Hello everyone, welcome back.", translation="سلام به همگی، خوش آمدید."),
            TranslatedSegment(id=2, start=5.0, end=8.0, text="Today we will talk about something interesting.", translation="امروز درباره چیزی جالب صحبت می‌کنیم."),
            TranslatedSegment(id=3, start=10.0, end=14.0, text="Let's get started right away.", translation="بیایید همین حالا شروع کنیم."),
        ],
    )

    # Save transcript + translation so resume would work too.
    from app.services import transcription, translation as translation_svc
    transcription.save_transcript(transcript, paths.transcript_path)
    translation_svc.save_translation(translation, paths.translation_path)
    log.info("Saved synthetic transcript + translation")

    # Clear any old TTS artifacts so we test fresh.
    import shutil
    if paths.tts.exists():
        shutil.rmtree(paths.tts)
    paths.tts.mkdir(parents=True, exist_ok=True)
    if paths.timing_path.exists():
        paths.timing_path.unlink()

    # Run synchronization (real TTS + real timing + real ffmpeg).
    log.info("Running synchronization pipeline...")
    final_audio = synchronization.synchronize(
        translation, provider="edge", voice="fa-IR-DilaraNeural",
        paths=paths, total_duration=dur,
    )
    log.info("Final dubbed audio: %s", final_audio)
    if not final_audio.exists():
        log.error("Synchronization did not produce a final audio file")
        return 1

    # Mux video + dubbed audio into a final MP4.
    out_path = paths.output / "integration_test.mp4"
    log.info("Rendering final video to %s", out_path)
    ffmpeg.mux_video_audio(paths.video_path, final_audio, out_path, crf=28)
    if not out_path.exists():
        log.error("Render produced no file")
        return 1
    out_dur = ffmpeg.probe_duration(out_path)
    log.info("SUCCESS: output video %s (%.2fs, %.1f KB)", out_path, out_dur, out_path.stat().st_size / 1024)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
