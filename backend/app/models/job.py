"""Pydantic models for transcripts and jobs.

These are the canonical data shapes used across services and the API.
"""
from __future__ import annotations

from typing import List, Optional

from pydantic import BaseModel, Field


# A single Whisper segment with timing.
class Segment(BaseModel):
    id: int
    start: float
    end: float
    text: str


class Transcript(BaseModel):
    """Full transcript = list of segments + detected language."""

    language: Optional[str] = None
    duration: Optional[float] = None
    segments: List[Segment] = Field(default_factory=list)


class TranslatedSegment(BaseModel):
    id: int
    start: float
    end: float
    text: str
    translation: str = ""


class Translation(BaseModel):
    source_language: Optional[str] = None
    target_language: str
    segments: List[TranslatedSegment] = Field(default_factory=list)


# --- Job statuses (state machine) ---
JOB_STATUSES = [
    "queued",
    "downloading",
    "extracting_audio",
    "transcribing",
    "translating",
    "generating_voice",
    "synchronizing",
    "rendering",
    "completed",
    "cancelled",
    "failed",
]

# Ordered pipeline stages for the progress UI.
PIPELINE_STAGES = [
    ("downloading", "دریافت ویدیو"),
    ("extracting_audio", "استخراج صدا"),
    ("transcribing", "تبدیل گفتار به متن"),
    ("translating", "ترجمه با Gemini"),
    ("generating_voice", "تولید صدای دوبله"),
    ("synchronizing", "هماهنگ‌سازی زمان‌بندی"),
    ("rendering", "رندر نهایی ویدیو"),
    ("completed", "تکمیل شد"),
]


# --- API request / response models ---
class VideoInspectRequest(BaseModel):
    url: str


class VideoInfo(BaseModel):
    video_id: str
    title: str
    channel: str = ""
    duration: float = 0.0
    thumbnail: str = ""
    available_qualities: List[str] = Field(default_factory=list)
    url: str


class CreateJobRequest(BaseModel):
    url: str
    source_lang: str = "auto"
    target_lang: str = "fa"
    tts_provider: str = "edge"
    tts_voice: str = ""
    keep_original_audio: bool = False
    original_audio_volume: float = 0.2
    dub_audio_volume: float = 1.0
    output_format: str = "mp4"


class JobCreatedResponse(BaseModel):
    job_id: str
    status: str = "queued"


class JobStatus(BaseModel):
    job_id: str
    status: str
    progress: int = 0
    stage: Optional[str] = None
    error: Optional[str] = None
    title: Optional[str] = None
    target_lang: str = "fa"
    output_format: str = "mp4"


class SettingsUpdate(BaseModel):
    """User-supplied Gemini key from the UI. Stored only in memory per process."""
    gemini_api_key: str = ""


class SettingsView(BaseModel):
    has_gemini_key: bool
    whisper_model: str
    tts_provider: str
    tts_default_voice: str
    available_voices: List[dict] = Field(default_factory=list)
    resources: dict = Field(default_factory=dict)
