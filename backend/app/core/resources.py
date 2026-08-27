"""Runtime resource detection: CPU/RAM/GPU.

Used at startup to pick a sensible Whisper model and device.
"""
from __future__ import annotations

import os
import shutil
from dataclasses import dataclass
from typing import Optional


@dataclass
class Resources:
    cpu_count: int
    ram_gb: float
    has_cuda: bool
    cuda_device_name: Optional[str]
    ffmpeg_available: bool
    yt_dlp_available: bool

    def to_dict(self) -> dict:
        return {
            "cpu_count": self.cpu_count,
            "ram_gb": round(self.ram_gb, 2),
            "has_cuda": self.has_cuda,
            "cuda_device_name": self.cuda_device_name,
            "ffmpeg_available": self.ffmpeg_available,
            "yt_dlp_available": self.yt_dlp_available,
        }


def detect_resources() -> Resources:
    cpu_count = os.cpu_count() or 1
    ram_gb = _detect_ram_gb()
    has_cuda, cuda_name = _detect_cuda()
    return Resources(
        cpu_count=cpu_count,
        ram_gb=ram_gb,
        has_cuda=has_cuda,
        cuda_device_name=cuda_name,
        ffmpeg_available=shutil.which("ffmpeg") is not None,
        yt_dlp_available=shutil.which("yt-dlp") is not None,
    )


def _detect_ram_gb() -> float:
    try:
        with open("/proc/meminfo", "r") as fh:
            for line in fh:
                if line.startswith("MemAvailable:"):
                    kb = int(line.split()[1])
                    return kb / (1024 * 1024)
    except Exception:
        pass
    return 0.0


def _detect_cuda():
    try:
        import ctranslate2  # type: ignore

        if ctranslate2.get_cuda_device_count() > 0:
            return True, ctranslate2.get_device_description(0)
    except Exception:
        pass
    return False, None


def recommended_whisper_model(resources: Resources, configured: str = "auto") -> str:
    """Pick a Whisper model based on resources if user set 'auto'."""
    if configured != "auto":
        return configured
    # Heuristics:
    # - GPU available -> medium
    # - >=8GB RAM, 4+ cores -> small
    # - 4-8GB RAM -> base
    # - <4GB RAM -> tiny
    if resources.has_cuda:
        return "medium"
    if resources.ram_gb >= 8 and resources.cpu_count >= 4:
        return "small"
    if resources.ram_gb >= 3:
        return "base"
    return "tiny"
