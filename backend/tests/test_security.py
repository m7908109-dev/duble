"""Tests for YouTube URL validation and security helpers."""
import pytest

from app.core.security import (
    extract_video_id,
    is_valid_youtube_url,
    sanitize_filename,
    assert_safe_job_id,
    UnsafePathError,
    InvalidYouTubeURL,
    redact,
    is_safe_subpath,
)
from pathlib import Path


@pytest.mark.parametrize(
    "url,expected_id",
    [
        ("https://www.youtube.com/watch?v=dQw4w9WgXcQ", "dQw4w9WgXcQ"),
        ("https://youtube.com/watch?v=dQw4w9WgXcQ", "dQw4w9WgXcQ"),
        ("https://youtu.be/dQw4w9WgXcQ", "dQw4w9WgXcQ"),
        ("https://www.youtube.com/embed/dQw4w9WgXcQ", "dQw4w9WgXcQ"),
        ("https://www.youtube.com/shorts/dQw4w9WgXcQ", "dQw4w9WgXcQ"),
        ("https://www.youtube.com/live/dQw4w9WgXcQ", "dQw4w9WgXcQ"),
        ("https://m.youtube.com/watch?v=abcdefghijk&t=10s", "abcdefghijk"),
        ("https://youtube-nocookie.com/embed/dQw4w9WgXcQ", "dQw4w9WgXcQ"),
    ],
)
def test_extract_video_id_valid(url, expected_id):
    assert extract_video_id(url) == expected_id
    assert is_valid_youtube_url(url) is True


@pytest.mark.parametrize(
    "url",
    [
        "",
        "not a url",
        "https://example.com/watch?v=dQw4w9WgXcQ",
        "https://youtube.com/watch?v=short",
        "https://youtube.com/watch?v=dQw4w9WgXcQ!@#",
        "ftp://youtube.com/watch?v=dQw4w9WgXcQ",
        "https://vimeo.com/12345",
        "https://youtube.com/other/dQw4w9WgXcQ",
    ],
)
def test_extract_video_id_invalid(url):
    assert is_valid_youtube_url(url) is False
    with pytest.raises(InvalidYouTubeURL):
        extract_video_id(url)


def test_sanitize_filename_basic():
    assert sanitize_filename("hello world.mp4") == "hello world.mp4"
    # Path separators are replaced with _; leading dots are stripped so the
    # result is a flat, safe filename with no directory traversal.
    assert sanitize_filename("../../etc/passwd") == "_.._etc_passwd"
    assert sanitize_filename("video (4K).mp4") == "video _4K_.mp4"
    assert sanitize_filename("") == "untitled"
    assert sanitize_filename("   ") == "untitled"


def test_sanitize_filename_max_len():
    name = "a" * 200
    out = sanitize_filename(name, max_len=50)
    assert len(out) == 50


def test_sanitize_filename_strips_unicode_accents():
    # Accented chars get normalized away to keep filenames portable.
    out = sanitize_filename("café résumé.mp4")
    assert "é" not in out
    assert "mp4" in out


def test_assert_safe_job_id_accepts_valid_uuid():
    assert_safe_job_id("5427297f-f8bb-47c7-b3dc-756d5d6adf51")


@pytest.mark.parametrize(
    "bad",
    [
        "not-a-uuid",
        "5427297f-f8bb-47c7-b3dc-756d5d6adf51.exe",
        "../../etc/passwd",
        "5427297f-f8bb-47c7-b3dc-756d5d6adf5X",
        "",
    ],
)
def test_assert_safe_job_id_rejects_bad(bad):
    with pytest.raises(UnsafePathError):
        assert_safe_job_id(bad)


def test_redact_masks_api_keys():
    text = "Using key AIzaSyABCDEFGHIJKLMNOPQRSTUVWXYZ1234567890 for the request"
    out = redact(text)
    assert "AIzaSyABCDEFGHIJKLMNOPQRSTUVWXYZ1234567890" not in out
    assert "[REDACTED]" in out


def test_redact_empty():
    assert redact("") == ""
    assert redact(None) is None


def test_is_safe_subpath(tmp_path):
    base = tmp_path / "jobs"
    base.mkdir()
    inside = base / "abc" / "input"
    inside.mkdir(parents=True)
    outside = tmp_path / "etc"
    outside.mkdir()
    assert is_safe_subpath(base, inside) is True
    assert is_safe_subpath(base, outside) is False
