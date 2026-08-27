"""Filesystem path helpers for a job's storage layout.

Layout for each job:
    storage/jobs/{job_id}/
        input/        downloaded video + metadata
        audio/       extracted wav
        transcript/  transcript.json
        translation/ translation.json
        tts/         generated dub audio clips + timing.json
        output/      final dubbed video
        logs/        per-job log file
"""
from __future__ import annotations

from pathlib import Path

from app.core.config import settings
from app.core.security import assert_safe_job_id


class JobPaths:
    """Strongly-typed paths for a single job."""

    def __init__(self, job_id: str) -> None:
        assert_safe_job_id(job_id)
        self.job_id = job_id
        self.root: Path = settings.jobs_path / job_id
        self.input: Path = self.root / "input"
        self.audio: Path = self.root / "audio"
        self.transcript: Path = self.root / "transcript"
        self.translation: Path = self.root / "translation"
        self.tts: Path = self.root / "tts"
        self.output: Path = self.root / "output"
        self.logs: Path = self.root / "logs"

    def ensure(self) -> "JobPaths":
        for p in (
            self.root,
            self.input,
            self.audio,
            self.transcript,
            self.translation,
            self.tts,
            self.output,
            self.logs,
        ):
            p.mkdir(parents=True, exist_ok=True)
        return self

    @property
    def metadata_path(self) -> Path:
        return self.input / "metadata.json"

    @property
    def video_path(self) -> Path:
        return self.input / "video.mp4"

    @property
    def audio_path(self) -> Path:
        return self.audio / "audio.wav"

    @property
    def transcript_path(self) -> Path:
        return self.transcript / "transcript.json"

    @property
    def translation_path(self) -> Path:
        return self.translation / "translation.json"

    @property
    def timing_path(self) -> Path:
        return self.tts / "timing.json"

    @property
    def mixed_audio_path(self) -> Path:
        return self.audio / "dubbed.wav"

    @property
    def output_path(self) -> Path:
        return self.output / f"dubbed.{settings.output_format}"

    @property
    def log_path(self) -> Path:
        return self.logs / "job.log"
