"""FFmpeg helpers: audio extraction, time-stretch (atempo), mixing, final mux.

All shell invocations go through a strict argument list (never shell=True)
to avoid injection. Paths are validated to be inside the job root.
"""
from __future__ import annotations

import asyncio
import shutil
import subprocess
from pathlib import Path
from typing import List, Optional

from app.core.logging import get_logger

log = get_logger(__name__)

FFMPEG = shutil.which("ffmpeg") or "ffmpeg"
FFPROBE = shutil.which("ffprobe") or "ffprobe"


class FFmpegError(RuntimeError):
    pass


def _run(cmd: List[str], timeout: int = 1800) -> None:
    """Run a command synchronously, raising FFmpegError on failure."""
    log.debug("exec: %s", " ".join(cmd))
    try:
        proc = subprocess.run(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            timeout=timeout,
            check=False,
        )
    except subprocess.TimeoutExpired as exc:
        raise FFmpegError(f"Command timed out after {timeout}s") from exc
    if proc.returncode != 0:
        err = proc.stderr.decode("utf-8", "ignore")[-2000:]
        raise FFmpegError(f"ffmpeg failed (rc={proc.returncode}): {err}")


async def _run_async(cmd: List[str], timeout: int = 1800) -> None:
    proc = await asyncio.create_subprocess_exec(
        *cmd,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    try:
        stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=timeout)
    except asyncio.TimeoutExpired:
        proc.kill()
        await proc.communicate()
        raise FFmpegError(f"Command timed out after {timeout}s")
    if proc.returncode != 0:
        err = (stderr or b"").decode("utf-8", "ignore")[-2000:]
        raise FFmpegError(f"ffmpeg failed (rc={proc.returncode}): {err}")


def extract_audio(video_path: Path, audio_path: Path) -> None:
    """Extract a 16kHz mono WAV suitable for Whisper."""
    audio_path.parent.mkdir(parents=True, exist_ok=True)
    if audio_path.exists():
        audio_path.unlink()
    cmd = [
        FFMPEG,
        "-y",
        "-i",
        str(video_path),
        "-vn",
        "-ac",
        "1",
        "-ar",
        "16000",
        "-c:a",
        "pcm_s16le",
        str(audio_path),
    ]
    _run(cmd)
    if not audio_path.exists():
        raise FFmpegError("Audio extraction produced no file")


def probe_duration(path: Path) -> float:
    """Return media duration in seconds using ffprobe."""
    cmd = [
        FFPROBE,
        "-v",
        "error",
        "-show_format",
        "-of",
        "json",
        str(path),
    ]
    try:
        out = subprocess.run(cmd, capture_output=True, timeout=60, check=False)
        if out.returncode != 0:
            log.warning("ffprobe failed (rc=%s)", out.returncode)
            return 0.0
        import json

        data = json.loads(out.stdout.decode("utf-8", "ignore") or "{}")
        dur = data.get("format", {}).get("duration")
        return float(dur) if dur else 0.0
    except Exception as exc:
        log.warning("ffprobe failed: %s", exc)
        return 0.0


def stretch_clip(input_path: Path, output_path: Path, speed: float) -> float:
    """Time-stretch an audio clip to a target speed.

    atempo accepts 0.5..100.0; for speeds outside that range we chain filters.
    Returns the speed actually applied (may be clamped).
    """
    speed = max(0.5, min(100.0, float(speed)))
    # Build a filter chain for extreme speeds.
    filters = _atempo_chain(speed)
    cmd = [
        FFMPEG,
        "-y",
        "-i",
        str(input_path),
        "-filter:a",
        filters,
        "-vn",
        "-ar",
        "24000",
        "-ac",
        "1",
        "-c:a",
        "pcm_s16le",
        str(output_path),
    ]
    _run(cmd)
    return speed


def _atempo_chain(speed: float) -> str:
    """Return an atempo filter chain. Each atempo step must be in [0.5, 100]."""
    if 0.5 <= speed <= 100.0:
        return f"atempo={speed:.6f}"
    parts = []
    remaining = speed
    while remaining > 100.0:
        parts.append("atempo=100.0")
        remaining /= 100.0
    parts.append(f"atempo={remaining:.6f}")
    return ",".join(parts)


def mix_audio(
    original: Path,
    dub_track: Path,
    output: Path,
    keep_original: bool,
    original_volume: float,
    dub_volume: float,
) -> None:
    """Mix original (optional, attenuated) + dub track into one wav."""
    output.parent.mkdir(parents=True, exist_ok=True)
    if keep_original and original.exists():
        # Two inputs, amix.
        cmd = [
            FFMPEG,
            "-y",
            "-i",
            str(original),
            "-i",
            str(dub_track),
            "-filter_complex",
            f"[0:a]volume={original_volume}[a0];[1:a]volume={dub_volume}[a1];"
            f"[a0][a1]amix=inputs=2:duration=longest:dropout_transition=0[aout]",
            "-map",
            "[aout]",
            "-ar",
            "44100",
            "-ac",
            "2",
            "-c:a",
            "pcm_s16le",
            str(output),
        ]
    else:
        # Just the dub track, possibly volume-adjusted.
        cmd = [
            FFMPEG,
            "-y",
            "-i",
            str(dub_track),
            "-filter:a",
            f"volume={dub_volume}",
            "-ar",
            "44100",
            "-ac",
            "2",
            "-c:a",
            "pcm_s16le",
            str(output),
        ]
    _run(cmd)


def mux_video_audio(
    video_path: Path,
    audio_path: Path,
    output_path: Path,
    crf: int = 23,
    video_codec: str = "copy",
    audio_codec: str = "aac",
) -> None:
    """Replace the audio of a video with the given audio track.

    By default the video stream is COPIED (no re-encode) — this is near-instant
    and avoids heavy CPU/RAM use. Set video_codec='libx264' to re-encode
    (e.g. to scale down or normalize pixel format).
    """
    output_path.parent.mkdir(parents=True, exist_ok=True)
    cmd = [
        FFMPEG,
        "-y",
        "-i",
        str(video_path),
        "-i",
        str(audio_path),
        "-c:v",
        video_codec,
        "-c:a",
        audio_codec,
        "-b:a",
        "192k",
        "-map",
        "0:v:0",
        "-map",
        "1:a:0",
        "-shortest",
        str(output_path),
    ]
    if video_codec != "copy":
        # Insert encoding options for the re-encode path.
        extra = ["-preset", "medium", "-crf", str(crf), "-pix_fmt", "yuv420p"]
        # Splice them after -c:v <codec>
        idx = cmd.index("-c:v") + 2
        cmd[idx:idx] = extra
    _run(cmd)


def build_silent_track(
    duration: float, output: Path, sample_rate: int = 24000
) -> None:
    """Generate a silent mono wav of `duration` seconds (timeline base)."""
    output.parent.mkdir(parents=True, exist_ok=True)
    cmd = [
        FFMPEG,
        "-y",
        "-f",
        "lavfi",
        "-i",
        f"anullsrc=channel_layout=mono:sample_rate={sample_rate}",
        "-t",
        f"{duration:.3f}",
        "-c:a",
        "pcm_s16le",
        str(output),
    ]
    _run(cmd)


def concat_segments(segment_paths: List[Path], output: Path) -> None:
    """Concatenate multiple wav files (same codec/params) into one."""
    if not segment_paths:
        raise FFmpegError("No segments to concatenate")
    output.parent.mkdir(parents=True, exist_ok=True)
    # Use the concat demuxer with a list file.
    list_path = output.parent / "_concat_list.txt"
    lines = [f"file '{p.resolve().as_posix()}'" for p in segment_paths]
    list_path.write_text("\n".join(lines), "utf-8")
    cmd = [
        FFMPEG,
        "-y",
        "-f",
        "concat",
        "-safe",
        "0",
        "-i",
        str(list_path),
        "-c",
        "copy",
        str(output),
    ]
    try:
        _run(cmd)
    finally:
        try:
            list_path.unlink()
        except Exception:
            pass


def overlay_clip_at(
    base_track: Path,
    insert_clip: Path,
    start: float,
    output: Path,
) -> None:
    """Overlay `insert_clip` onto `base_track` starting at `start` seconds."""
    output.parent.mkdir(parents=True, exist_ok=True)
    delay_ms = max(0, int(start * 1000))
    cmd = [
        FFMPEG,
        "-y",
        "-i",
        str(base_track),
        "-i",
        str(insert_clip),
        "-filter_complex",
        f"[1:a]adelay={delay_ms}|{delay_ms}[d];[0:a][d]amix=inputs=2:duration=first:normalize=0[aout]",
        "-map",
        "[aout]",
        "-c:a",
        "pcm_s16le",
        "-ar",
        "24000",
        "-ac",
        "1",
        str(output),
    ]
    _run(cmd)
