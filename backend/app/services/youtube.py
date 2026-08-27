"""YouTube service: metadata + download, built on yt-dlp.

We respect YouTube's access controls — yt-dlp will fail on private/age-gated
videos, which is the intended behavior. We do NOT attempt to bypass any
restriction.
"""
from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any, Dict, List, Optional

import yt_dlp

from app.core.config import settings
from app.core.logging import get_logger
from app.core.security import extract_video_id, is_safe_subpath

log = get_logger(__name__)


class YouTubeError(RuntimeError):
    pass


@dataclass
class VideoMetadata:
    video_id: str
    title: str
    channel: str
    duration: float
    thumbnail: str
    url: str
    available_qualities: List[str]

    def to_dict(self) -> dict:
        return {
            "video_id": self.video_id,
            "title": self.title,
            "channel": self.channel,
            "duration": self.duration,
            "thumbnail": self.thumbnail,
            "url": self.url,
            "available_qualities": self.available_qualities,
        }


def _ydl_base_opts() -> Dict[str, Any]:
    return {
        "quiet": True,
        "no_warnings": True,
        "noprogress": True,
        "noplaylist": True,
        # Stay polite, avoid captcha triggers.
        "retries": 5,
        "fragment_retries": 5,
    }


def inspect(url: str) -> VideoMetadata:
    """Fetch metadata without downloading."""
    video_id = extract_video_id(url)
    canonical = f"https://www.youtube.com/watch?v={video_id}"
    opts = _ydl_base_opts()
    opts["skip_download"] = True
    opts["listformats"] = False
    try:
        with yt_dlp.YoutubeDL(opts) as ydl:
            info = ydl.extract_info(canonical, download=False)
    except yt_dlp.utils.DownloadError as exc:
        raise YouTubeError(f"Could not fetch video info: {exc}") from exc
    if not info:
        raise YouTubeError("Empty video info returned")
    qualities = _collect_qualities(info)
    thumb = ""
    thumbnails = info.get("thumbnails") or []
    if thumbnails:
        # Pick the largest reasonable thumbnail.
        thumb = thumbnails[-1].get("url", "")
    if not thumb:
        thumb = f"https://i.ytimg.com/vi/{video_id}/hqdefault.jpg"
    return VideoMetadata(
        video_id=video_id,
        title=info.get("title") or "Untitled",
        channel=info.get("channel") or info.get("uploader") or "",
        duration=float(info.get("duration") or 0.0),
        thumbnail=thumb,
        url=canonical,
        available_qualities=qualities,
    )


def _collect_qualities(info: dict) -> List[str]:
    formats = info.get("formats") or []
    seen = []
    out = []
    for f in formats:
        h = f.get("height")
        if h and f.get("vcodec") != "none":
            label = f"{h}p"
            if label not in seen:
                seen.append(label)
                out.append(label)
    # Sort descending by numeric height.
    out.sort(key=lambda x: int(x[:-1]), reverse=True)
    return out


def download(url: str, dest_dir, max_duration: Optional[float] = None) -> str:
    """Download a YouTube video as mp4 to dest_dir. Returns the file path.

    We pick a progressive (audio+video) mp4 when available; otherwise we
    download best video + best audio and merge with ffmpeg.
    """
    import os
    from pathlib import Path

    dest = Path(dest_dir)
    dest.mkdir(parents=True, exist_ok=True)
    video_id = extract_video_id(url)
    canonical = f"https://www.youtube.com/watch?v={video_id}"

    if max_duration and max_duration > 0:
        # Pre-check duration to refuse overly long videos.
        meta = inspect(url)
        if meta.duration > max_duration:
            raise YouTubeError(
                f"Video duration {int(meta.duration)}s exceeds max "
                f"{int(max_duration)}s allowed by the server."
            )

    out_template = str(dest / "video.%(ext)s")
    opts = _ydl_base_opts()
    opts.update(
        {
            # Prefer a 720p (or lower) progressive-friendly format that keeps
            # file sizes and CPU encode cost reasonable on Codespaces.
            # Fallbacks ensure we still get SOMETHING if 720p is unavailable.
            "format": (
                "bestvideo[height<=720][ext=mp4]+bestaudio[ext=m4a]/"
                "bestvideo[height<=720]+bestaudio/"
                "best[height<=720][ext=mp4]/"
                "best[ext=mp4]/best"
            ),
            "outtmpl": out_template,
            "merge_output_format": "mp4",
            "max_filesize": settings.max_download_mb * 1024 * 1024,
        }
    )
    try:
        with yt_dlp.YoutubeDL(opts) as ydl:
            info = ydl.extract_info(canonical, download=True)
    except yt_dlp.utils.DownloadError as exc:
        raise YouTubeError(f"Download failed: {exc}") from exc

    # Resolve the final path.
    expected = dest / "video.mp4"
    if expected.exists():
        return str(expected)
    # Fallback: search for any video.* in dest.
    for cand in dest.iterdir():
        if cand.is_file() and cand.name.startswith("video."):
            return str(cand)
    raise YouTubeError("Download completed but output file was not found")


def write_metadata(meta: VideoMetadata, dest_path) -> None:
    """Persist metadata.json so the resume system can reuse it."""
    from pathlib import Path

    path = Path(dest_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(meta.to_dict(), ensure_ascii=False, indent=2), "utf-8")
