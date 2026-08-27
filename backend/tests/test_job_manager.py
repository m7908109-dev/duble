"""Tests for job state machine and lifecycle (uses a temp SQLite db)."""
import asyncio
import uuid

import pytest

from app.core.config import settings
from app.models import database
from app.models.job import CreateJobRequest, JOB_STATUSES
from app.workers.job_manager import JobManager


def _setup_db(tmp_path):
    """Synchronously initialize the DB in the temp storage dir."""
    settings.storage_dir = str(tmp_path)
    asyncio.run(database.init_db())


def _make_req(url="https://www.youtube.com/watch?v=dQw4w9WgXcQ") -> CreateJobRequest:
    return CreateJobRequest(
        url=url,
        source_lang="auto",
        target_lang="fa",
        tts_provider="edge",
        tts_voice="fa-IR-DilaraNeural",
        keep_original_audio=False,
        original_audio_volume=0.2,
        dub_audio_volume=1.0,
        output_format="mp4",
    )


@pytest.fixture
def fresh_db(tmp_path, monkeypatch):
    monkeypatch.setattr(settings, "storage_dir", str(tmp_path))
    monkeypatch.setattr(settings, "max_concurrent_jobs", 1)
    _setup_db(tmp_path)
    yield


@pytest.mark.asyncio
async def test_create_job_persists_queued(fresh_db):
    mgr = JobManager()
    job_id = await mgr.create_job(_make_req())
    status = await mgr.get_status(job_id)
    assert status is not None
    assert status["status"] == "queued"
    assert status["target_lang"] == "fa"
    assert status["tts_voice"] == "fa-IR-DilaraNeural"
    assert status["keep_original_audio"] == 0


@pytest.mark.asyncio
async def test_cancel_job_sets_status(fresh_db):
    mgr = JobManager()
    job_id = await mgr.create_job(_make_req())
    await mgr.cancel_job(job_id)
    status = await mgr.get_status(job_id)
    assert status["status"] == "cancelled"


@pytest.mark.asyncio
async def test_invalid_url_rejected(fresh_db):
    from app.core.security import InvalidYouTubeURL

    mgr = JobManager()
    with pytest.raises(InvalidYouTubeURL):
        await mgr.create_job(_make_req("https://vimeo.com/12345"))


@pytest.mark.asyncio
async def test_list_jobs_returns_recent_first(fresh_db):
    mgr = JobManager()
    j1 = await mgr.create_job(_make_req())
    j2 = await mgr.create_job(_make_req())
    jobs = await mgr.list_jobs(limit=10)
    assert len(jobs) >= 2
    # Most recent first.
    assert jobs[0]["job_id"] == j2
    assert jobs[1]["job_id"] == j1


@pytest.mark.asyncio
async def test_get_unknown_job_returns_none(fresh_db):
    mgr = JobManager()
    status = await mgr.get_status(str(uuid.uuid4()))
    assert status is None


def test_job_statuses_contains_all_states():
    expected = {
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
    }
    assert set(JOB_STATUSES) == expected
