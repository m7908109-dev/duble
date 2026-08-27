"""API routes: jobs lifecycle + SSE + transcript/translation/video outputs."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse, JSONResponse
from sse_starlette.sse import EventSourceResponse

from app.core.config import settings
from app.core.security import InvalidYouTubeURL, UnsafePathError, assert_safe_job_id
from app.models.job import CreateJobRequest, JobCreatedResponse, JobStatus
from app.services import transcription, translation
from app.utils.paths import JobPaths
from app.workers.job_manager import manager

router = APIRouter(prefix="/api/jobs", tags=["jobs"])


@router.post("", response_model=JobCreatedResponse)
async def create_job(req: CreateJobRequest) -> JobCreatedResponse:
    try:
        job_id = await manager.create_job(req)
    except InvalidYouTubeURL as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    except RuntimeError as exc:
        raise HTTPException(status_code=429, detail=str(exc))
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Could not create job: {exc}")
    return JobCreatedResponse(job_id=job_id, status="queued")


@router.get("", response_model=list[dict])
async def list_jobs(limit: int = 50) -> list[dict]:
    return await manager.list_jobs(limit=limit)


@router.get("/{job_id}", response_model=JobStatus)
async def get_job(job_id: str) -> JobStatus:
    try:
        assert_safe_job_id(job_id)
    except UnsafePathError:
        raise HTTPException(status_code=400, detail="Invalid job id")
    status = await manager.get_status(job_id)
    if not status:
        raise HTTPException(status_code=404, detail="Job not found")
    return JobStatus(
        job_id=status["job_id"],
        status=status["status"],
        progress=status["progress"],
        stage=status.get("stage"),
        error=status.get("error"),
        title=status.get("title"),
        target_lang=status.get("target_lang", "fa"),
        output_format=status.get("output_format", "mp4"),
    )


@router.post("/{job_id}/cancel")
async def cancel_job(job_id: str) -> dict:
    try:
        assert_safe_job_id(job_id)
    except UnsafePathError:
        raise HTTPException(status_code=400, detail="Invalid job id")
    status = await manager.get_status(job_id)
    if not status:
        raise HTTPException(status_code=404, detail="Job not found")
    await manager.cancel_job(job_id)
    return {"ok": True, "status": "cancelled"}


@router.get("/{job_id}/events")
async def job_events(job_id: str):
    try:
        assert_safe_job_id(job_id)
    except UnsafePathError:
        raise HTTPException(status_code=400, detail="Invalid job id")
    status = await manager.get_status(job_id)
    if not status:
        raise HTTPException(status_code=404, detail="Job not found")

    async def event_generator():
        q = await manager.subscribe(job_id)
        try:
            while True:
                payload = await q.get()
                yield {"event": "status", "data": json.dumps(payload, ensure_ascii=False)}
                # If terminal, send one final message and stop.
                if payload.get("status") in ("completed", "failed", "cancelled"):
                    yield {
                        "event": "done",
                        "data": json.dumps({"status": payload["status"]}, ensure_ascii=False),
                    }
                    break
        finally:
            await manager.unsubscribe(job_id, q)

    return EventSourceResponse(event_generator())


@router.get("/{job_id}/transcript")
async def get_transcript(job_id: str) -> JSONResponse:
    try:
        assert_safe_job_id(job_id)
    except UnsafePathError:
        raise HTTPException(status_code=400, detail="Invalid job id")
    paths = JobPaths(job_id)
    if not paths.transcript_path.exists():
        raise HTTPException(status_code=404, detail="Transcript not ready yet")
    data = json.loads(paths.transcript_path.read_text("utf-8"))
    return JSONResponse(data)


@router.get("/{job_id}/translation")
async def get_translation(job_id: str) -> JSONResponse:
    try:
        assert_safe_job_id(job_id)
    except UnsafePathError:
        raise HTTPException(status_code=400, detail="Invalid job id")
    paths = JobPaths(job_id)
    if not paths.translation_path.exists():
        raise HTTPException(status_code=404, detail="Translation not ready yet")
    data = json.loads(paths.translation_path.read_text("utf-8"))
    return JSONResponse(data)


@router.get("/{job_id}/video")
async def get_video(job_id: str):
    try:
        assert_safe_job_id(job_id)
    except UnsafePathError:
        raise HTTPException(status_code=400, detail="Invalid job id")
    status = await manager.get_status(job_id)
    if not status:
        raise HTTPException(status_code=404, detail="Job not found")
    if status["status"] != "completed":
        raise HTTPException(status_code=409, detail=f"Job not completed (status={status['status']})")
    paths = JobPaths(job_id)
    if not paths.output_path.exists():
        raise HTTPException(status_code=404, detail="Output video not found")
    return FileResponse(
        str(paths.output_path),
        media_type="video/mp4",
        filename=f"dubbed_{job_id[:8]}.{settings.output_format}",
    )


@router.post("/{job_id}/cleanup")
async def cleanup_job(job_id: str, keep_output: bool = True) -> dict:
    """Delete intermediate files; optionally keep the final output."""
    try:
        assert_safe_job_id(job_id)
    except UnsafePathError:
        raise HTTPException(status_code=400, detail="Invalid job id")
    paths = JobPaths(job_id)
    output = paths.output
    for sub in (paths.input, paths.audio, paths.transcript, paths.translation, paths.tts, paths.logs):
        if sub.exists():
            for f in sub.iterdir():
                try:
                    f.unlink()
                except Exception:
                    pass
    if not keep_output and output.exists():
        for f in output.iterdir():
            try:
                f.unlink()
            except Exception:
                pass
    return {"ok": True}
