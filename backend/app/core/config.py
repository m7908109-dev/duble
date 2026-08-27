"""Application configuration loaded from environment variables.

All secrets come from environment / .env file. They are NEVER logged,
NEVER returned in API responses, and NEVER written into the database.
"""
from __future__ import annotations

import os
from functools import lru_cache
from pathlib import Path
from typing import List

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Strongly-typed settings sourced from environment / .env."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )

    # --- Gemini ---
    gemini_api_key: str = Field(default="", alias="GEMINI_API_KEY")
    gemini_model: str = Field(default="gemini-2.0-flash", alias="GEMINI_MODEL")

    # --- Whisper ---
    whisper_model: str = Field(default="base", alias="WHISPER_MODEL")
    whisper_compute_type: str = Field(default="int8", alias="WHISPER_COMPUTE_TYPE")
    whisper_device: str = Field(default="auto", alias="WHISPER_DEVICE")
    whisper_beam_size: int = Field(default=5, alias="WHISPER_BEAM_SIZE")

    # --- TTS ---
    tts_provider: str = Field(default="edge", alias="TTS_PROVIDER")
    tts_default_voice: str = Field(
        default="fa-IR-GhazalNeural", alias="TTS_DEFAULT_VOICE"
    )
    piper_model_path: str = Field(default="", alias="PIPER_MODEL_PATH")
    piper_config_path: str = Field(default="", alias="PIPER_CONFIG_PATH")

    # --- Server ---
    host: str = Field(default="0.0.0.0", alias="HOST")
    port: int = Field(default=8000, alias="PORT")
    app_secret: str = Field(default="change-me-please", alias="APP_SECRET")
    # CORS allowed origins. The Next.js dev server runs on :3000.
    cors_origins: List[str] = Field(default_factory=lambda: ["*"])

    # --- Storage ---
    storage_dir: str = Field(default="./storage", alias="STORAGE_DIR")

    # --- Limits ---
    max_concurrent_jobs: int = Field(default=1, alias="MAX_CONCURRENT_JOBS")
    max_video_duration_seconds: int = Field(
        default=0, alias="MAX_VIDEO_DURATION_SECONDS"
    )
    max_download_mb: int = Field(default=2048, alias="MAX_DOWNLOAD_MB")
    output_format: str = Field(default="mp4", alias="OUTPUT_FORMAT")
    output_crf: int = Field(default=23, alias="OUTPUT_CRF")

    # --- Sync ---
    sync_max_speed: float = Field(default=1.30, alias="SYNC_MAX_SPEED")
    sync_min_speed: float = Field(default=0.80, alias="SYNC_MIN_SPEED")

    # --- Derived at runtime, NOT from env ---
    @property
    def storage_path(self) -> Path:
        p = Path(self.storage_dir).resolve()
        p.mkdir(parents=True, exist_ok=True)
        return p

    @property
    def jobs_path(self) -> Path:
        p = self.storage_path / "jobs"
        p.mkdir(parents=True, exist_ok=True)
        return p

    @property
    def db_path(self) -> Path:
        return self.storage_path / "dubbing.db"

    @property
    def has_gemini_key(self) -> bool:
        return bool(self.gemini_api_key and self.gemini_api_key.strip())


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Cached settings singleton."""
    return Settings()


# Module-level convenience for direct imports
settings = get_settings()
