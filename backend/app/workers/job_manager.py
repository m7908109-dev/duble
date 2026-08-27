"""In-process job manager.

Responsibilities:
  - Maintain an in-memory queue + running set with a max concurrency limit.
  - Persist state to SQLite on every transition.
  - Broadcast state changes over SSE (in-memory pub/sub).
  - Support resume: re-running a job skips stages whose artifacts exist.
  - Support cancellation via a cancel event.

We deliberately avoid Celery/Redis: for a single-machine Codespaces box,
an asyncio.Queue + a single worker task is enough and far simpler.
"""
from __future__ import annotations

import asyncio
import json
import traceback
import uuid
from datetime import datetime, timezone
from typing import Awaitable, Callable, Dict, List, Optional

from app.core.config import settings
from app.core.logging import get_logger
from app.core.security import extract_video_id, is_valid_youtube_url, InvalidYouTubeURL
from app.models import database
from app.models.job import CreateJobRequest, JOB_STATUSES
from app.services import dubbing
from app.services.dubbing import StageError

log = get_logger(__name__)


class JobManager:
    def __init__(self) -> None:
        self._queue: asyncio.Queue[str] = asyncio.Queue()
        self._running: Dict[str, asyncio.Task] = {}
        self._cancelled: set[str] = set()
        # Pub/sub for SSE: job_id -> list of asyncio.Queue
        self._subs: Dict[str, List[asyncio.Queue]] = {}
        self._subs_lock = asyncio.Lock()
        self._worker_task: Optional[asyncio.Task] = None
        self._started = False

    # ---------- lifecycle ----------
    def start(self) -> None:
        if self._started:
            return
        self._started = True
        self._worker_task = asyncio.create_task(self._worker_loop())
        # Re-enqueue any jobs left in a transient state (e.g. server restarted
        # mid-run). Transient stages get re-queued; terminal stages untouched.
        asyncio.create_task(self._reenqueue_transient())

    async def _reenqueue_transient(self) -> None:
        transient = {
            "queued",
            "downloading",
            "extracting_audio",
            "transcribing",
            "translating",
            "generating_voice",
            "synchronizing",
            "rendering",
        }
        conn = await database.get_conn()
        try:
            cur = await conn.execute(
                "SELECT job_id FROM jobs WHERE status IN (%s)"
                % ",".join("?" for _ in transient),
                tuple(transient),
            )
            rows = await cur.fetchall()
        finally:
            await conn.close()
        for r in rows:
            jid = r["job_id"]
            await self._set_status(jid, "queued", 0, None)
            await self._queue.put(jid)
            log.info("Re-enqueued transient job %s", jid)

    # ---------- API ----------
    async def create_job(self, req: CreateJobRequest) -> str:
        if not is_valid_youtube_url(req.url):
            raise InvalidYouTubeURL("Not a valid YouTube URL")
        if not settings.has_gemini_key:
            # We still allow creation; translation stage will fail clearly.
            log.warning("Creating job without a Gemini key configured")
        if len(self._running) >= settings.max_concurrent_jobs:
            raise RuntimeError(
                f"Max concurrent jobs ({settings.max_concurrent_jobs}) reached"
            )
        video_id = extract_video_id(req.url)
        job_id = str(uuid.uuid4())
        now = _now()
        # Resolve a default voice if not provided.
        if not req.tts_voice:
            from app.services.tts import registry

            prov = registry.get(req.tts_provider)
            req.tts_voice = prov.default_voice(req.target_lang)
        conn = await database.get_conn()
        try:
            await conn.execute(
                """INSERT INTO jobs
                (job_id, youtube_url, video_id, title, channel, duration, thumbnail,
                 source_lang, target_lang, tts_provider, tts_voice,
                 keep_original_audio, original_audio_volume, dub_audio_volume,
                 output_format, status, progress, stage, error,
                 created_at, updated_at)
                VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                (
                    job_id,
                    req.url,
                    video_id,
                    None,
                    None,
                    None,
                    None,
                    req.source_lang,
                    req.target_lang,
                    req.tts_provider,
                    req.tts_voice,
                    int(req.keep_original_audio),
                    float(req.original_audio_volume),
                    float(req.dub_audio_volume),
                    req.output_format,
                    "queued",
                    0,
                    None,
                    None,
                    now,
                    now,
                ),
            )
            await conn.commit()
        finally:
            await conn.close()
        await self._queue.put(job_id)
        return job_id

    async def cancel_job(self, job_id: str) -> None:
        self._cancelled.add(job_id)
        await self._set_status(job_id, "cancelled", 0, "cancelled")
        await self._broadcast(job_id, {"status": "cancelled", "progress": 0})

    def is_cancelled(self, job_id: str) -> bool:
        return job_id in self._cancelled

    # ---------- worker loop ----------
    async def _worker_loop(self) -> None:
        log.info("Job worker loop started (max_concurrent=%d)", settings.max_concurrent_jobs)
        while True:
            job_id = await self._queue.get()
            if job_id in self._cancelled:
                continue
            # Wait for a free slot if at capacity.
            while len(self._running) >= settings.max_concurrent_jobs:
                await asyncio.sleep(0.25)
            task = asyncio.create_task(self._run_one(job_id))
            self._running[job_id] = task
            task.add_done_callback(lambda t, jid=job_id: self._on_done(jid, t))

    def _on_done(self, job_id: str, task: asyncio.Task) -> None:
        self._running.pop(job_id, None)
        if task.cancelled():
            return
        exc = task.exception()
        if exc:
            log.error("Job %s ended with error: %s", job_id, exc)

    async def _run_one(self, job_id: str) -> None:
        log.info("Starting job %s", job_id)

        async def update(status: str, progress: int, stage: Optional[str]) -> None:
            if self.is_cancelled(job_id):
                raise StageError("Job cancelled")
            await self._set_status(job_id, status, progress, stage)
            await self._broadcast(
                job_id,
                {"status": status, "progress": progress, "stage": stage},
            )

        try:
            await self._set_status(job_id, "downloading", 5, "downloading")
            await dubbing.run_pipeline(job_id, update)
        except StageError as exc:
            log.warning("Job %s stage error: %s", job_id, exc)
            await self._fail(job_id, str(exc))
        except Exception as exc:
            log.error("Job %s unexpected error: %s\n%s", job_id, exc, traceback.format_exc())
            await self._fail(job_id, f"Unexpected error: {exc}")

    async def _fail(self, job_id: str, message: str) -> None:
        await self._set_status(job_id, "failed", 0, "failed", error=message)
        await self._broadcast(
            job_id, {"status": "failed", "progress": 0, "stage": "failed", "error": message}
        )

    # ---------- DB helpers ----------
    async def _set_status(
        self,
        job_id: str,
        status: str,
        progress: int,
        stage: Optional[str],
        error: Optional[str] = None,
    ) -> None:
        now = _now()
        completed = now if status in ("completed", "failed", "cancelled") else None
        conn = await database.get_conn()
        try:
            await conn.execute(
                """UPDATE jobs
                   SET status=?, progress=?, stage=?, error=?, updated_at=?, completed_at=?
                   WHERE job_id=?""",
                (status, progress, stage, error, now, completed, job_id),
            )
            await conn.commit()
        finally:
            await conn.close()

    async def get_status(self, job_id: str) -> Optional[dict]:
        conn = await database.get_conn()
        try:
            cur = await conn.execute("SELECT * FROM jobs WHERE job_id=?", (job_id,))
            row = await cur.fetchone()
        finally:
            await conn.close()
        if not row:
            return None
        return dict(row)

    async def list_jobs(self, limit: int = 50) -> List[dict]:
        conn = await database.get_conn()
        try:
            cur = await conn.execute(
                "SELECT * FROM jobs ORDER BY created_at DESC LIMIT ?", (limit,)
            )
            rows = await cur.fetchall()
        finally:
            await conn.close()
        return [dict(r) for r in rows]

    # ---------- SSE pub/sub ----------
    async def subscribe(self, job_id: str) -> asyncio.Queue:
        async with self._subs_lock:
            q: asyncio.Queue = asyncio.Queue(maxsize=100)
            self._subs.setdefault(job_id, []).append(q)
        # Send current state immediately.
        status = await self.get_status(job_id)
        if status:
            await q.put(
                {
                    "status": status["status"],
                    "progress": status["progress"],
                    "stage": status.get("stage"),
                    "error": status.get("error"),
                }
            )
        return q

    async def unsubscribe(self, job_id: str, q: asyncio.Queue) -> None:
        async with self._subs_lock:
            subs = self._subs.get(job_id, [])
            if q in subs:
                subs.remove(q)
            if not subs:
                self._subs.pop(job_id, None)

    async def _broadcast(self, job_id: str, payload: dict) -> None:
        async with self._subs_lock:
            subs = list(self._subs.get(job_id, []))
        for q in subs:
            try:
                q.put_nowait(payload)
            except asyncio.QueueFull:
                # Drop oldest and push newest.
                try:
                    q.get_nowait()
                    q.put_nowait(payload)
                except Exception:
                    pass


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


# Singleton.
manager = JobManager()
