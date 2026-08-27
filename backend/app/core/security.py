"""Security helpers: YouTube URL validation, path sanitization, secrets.

These functions are intentionally defensive and are unit-tested.
"""
from __future__ import annotations

import re
import unicodedata
from pathlib import Path
from urllib.parse import urlparse, parse_qs

# YouTube URL patterns.
# We accept the common share/embed formats. We do NOT bypass any access
# restrictions; the downloader itself respects YouTube's age/region controls.
_YT_HOSTS = {
    "youtube.com",
    "www.youtube.com",
    "m.youtube.com",
    "youtu.be",
    "www.youtu.be",
    "music.youtube.com",
    "youtube-nocookie.com",
    "www.youtube-nocookie.com",
}

# Path-traversal protection: a job_id may only contain hex/dash chars.
_JOB_ID_RE = re.compile(r"^[a-f0-9]{8}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{12}$")


class InvalidYouTubeURL(ValueError):
    """Raised when a URL is not a valid YouTube URL."""


class UnsafePathError(ValueError):
    """Raised when a path component looks suspicious."""


def extract_video_id(url: str) -> str:
    """Return the 11-char video id or raise InvalidYouTubeURL."""
    if not url or not isinstance(url, str):
        raise InvalidYouTubeURL("Empty URL")
    url = url.strip()
    try:
        parsed = urlparse(url)
    except Exception as exc:  # pragma: no cover - defensive
        raise InvalidYouTubeURL(f"Could not parse URL: {exc}") from exc

    if parsed.scheme not in ("http", "https"):
        raise InvalidYouTubeURL("URL must use http or https scheme")

    host = (parsed.netloc or "").lower()
    if host not in _YT_HOSTS:
        raise InvalidYouTubeURL(f"Host '{host}' is not a recognized YouTube host")

    query = parse_qs(parsed.query)
    vid = ""
    if "v" in query:
        vid = query["v"][0]
    elif host == "youtu.be":
        vid = parsed.path.lstrip("/")
    elif parsed.path.startswith("/embed/"):
        vid = parsed.path.split("/embed/", 1)[1].split("/")[0]
    elif parsed.path.startswith("/shorts/"):
        vid = parsed.path.split("/shorts/", 1)[1].split("/")[0]
    elif parsed.path.startswith("/live/"):
        vid = parsed.path.split("/live/", 1)[1].split("/")[0]

    vid = (vid or "").strip()
    if not re.fullmatch(r"[A-Za-z0-9_-]{11}", vid):
        raise InvalidYouTubeURL("Could not extract a valid YouTube video id")
    return vid


def is_valid_youtube_url(url: str) -> bool:
    try:
        extract_video_id(url)
        return True
    except InvalidYouTubeURL:
        return False


def sanitize_filename(name: str, max_len: int = 80) -> str:
    """Make a filename safe: strip path separators, control chars, accents."""
    if not name:
        return "untitled"
    # Normalize unicode (NFKD) and drop combining marks to avoid weird glyphs.
    name = unicodedata.normalize("NFKD", name)
    name = name.encode("ascii", "ignore").decode("ascii")
    name = re.sub(r"[^\w\-. ]", "_", name)
    name = re.sub(r"\s+", " ", name).strip()
    name = name.strip(".")
    if not name:
        name = "untitled"
    return name[:max_len]


def assert_safe_job_id(job_id: str) -> None:
    """Validate a job_id to prevent path traversal attacks."""
    if not isinstance(job_id, str) or not _JOB_ID_RE.fullmatch(job_id):
        raise UnsafePathError("Invalid job id format")


def redact(text: str) -> str:
    """Redact anything that looks like an API key from a string (for logging)."""
    if not text:
        return text
    # Mask common AI key patterns: long alnum strings.
    return re.sub(r"(AIza[0-9A-Za-z_\-]{20,})", "[REDACTED]", text)


def is_safe_subpath(base: Path, target: Path) -> bool:
    """Return True if `target` is inside `base` (no traversal escape)."""
    try:
        target.resolve().relative_to(base.resolve())
        return True
    except ValueError:
        return False
