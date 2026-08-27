"""Database access using aiosqlite (async SQLite).

Schema is intentionally simple and self-healing: we create tables on startup.
We store the job record + per-stage progress here. Large artifacts (transcript
JSON, audio files) live on the filesystem under storage/jobs/{job_id}/.
"""
from __future__ import annotations

import aiosqlite
from pathlib import Path

from app.core.config import settings
from app.core.logging import get_logger

log = get_logger(__name__)

SCHEMA = """
CREATE TABLE IF NOT EXISTS jobs (
    job_id TEXT PRIMARY KEY,
    youtube_url TEXT NOT NULL,
    video_id TEXT NOT NULL,
    title TEXT,
    channel TEXT,
    duration REAL,
    thumbnail TEXT,
    source_lang TEXT,
    target_lang TEXT NOT NULL,
    tts_provider TEXT NOT NULL,
    tts_voice TEXT NOT NULL,
    keep_original_audio INTEGER NOT NULL DEFAULT 0,
    original_audio_volume REAL NOT NULL DEFAULT 0.2,
    dub_audio_volume REAL NOT NULL DEFAULT 1.0,
    output_format TEXT NOT NULL DEFAULT 'mp4',
    status TEXT NOT NULL DEFAULT 'queued',
    progress INTEGER NOT NULL DEFAULT 0,
    stage TEXT,
    error TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    completed_at TEXT
);

CREATE INDEX IF NOT EXISTS idx_jobs_status ON jobs(status);
CREATE INDEX IF NOT EXISTS idx_jobs_created ON jobs(created_at);
"""


async def init_db() -> None:
    db_path: Path = settings.db_path
    db_path.parent.mkdir(parents=True, exist_ok=True)
    async with aiosqlite.connect(db_path) as conn:
        await conn.executescript(SCHEMA)
        await conn.commit()
    log.info("Database ready at %s", db_path)


async def get_conn() -> aiosqlite.Connection:
    conn = await aiosqlite.connect(settings.db_path)
    conn.row_factory = aiosqlite.Row
    await conn.execute("PRAGMA journal_mode=WAL;")
    await conn.execute("PRAGMA foreign_keys=ON;")
    return conn
