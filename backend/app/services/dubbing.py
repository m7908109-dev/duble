"""Dubbing pipeline orchestrator.

This module is the only place that knows the full end-to-end flow. It calls
each service (youtube, transcription, translation, tts, synchronization,
ffmpeg) in order, persisting intermediate artifacts so a crashed job can be
resumed from the last completed stage.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Optional

from app.core.config import settings
from app.core.logging import get_logger
from app.models import database
from app.services import ffmpeg, transcription, translation, youtube
from app.services.synchronization import synchronize
from app.utils.paths import JobPaths as JPaths

log = get_logger(__name__)


class StageError(RuntimeError):
    pass


def load_translation_or_none(paths: JPaths):
    try:
        return translation.load_translation(paths.translation_path)
    except FileNotFoundError:
        return None


def load_transcript_or_none(paths: JPaths):
    try:
        return transcription.load_transcript(paths.transcript_path)
    except FileNotFoundError:
        return None


async def run_pipeline(job_id: str, update) -> None:
    """Run the full pipeline for one job.

    `update` is an async callable: `await update(status, progress, stage)`
    that persists state to the DB and broadcasts an SSE event.
    """
    conn = await database.get_conn()
    try:
        cur = await conn.execute("SELECT * FROM jobs WHERE job_id=?", (job_id,))
        row = await cur.fetchone()
    finally:
        await conn.close()

    if not row:
        raise StageError(f"Job {job_id} not found")

    paths = JPaths(job_id).ensure()

    youtube_url = row["youtube_url"]
    source_lang = row["source_lang"] or "auto"
    target_lang = row["target_lang"]
    tts_provider = row["tts_provider"]
    tts_voice = row["tts_voice"]
    keep_original = bool(row["keep_original_audio"])
    orig_vol = float(row["original_audio_volume"])
    dub_vol = float(row["dub_audio_volume"])

    # ----- Stage: downloading -----
    if not paths.video_path.exists():
        await update("downloading", 5, "downloading")
        meta = youtube.inspect(youtube_url)
        youtube.download(
            youtube_url,
            paths.input,
            max_duration=settings.max_video_duration_seconds or None,
        )
        youtube.write_metadata(meta, paths.metadata_path)
        # Persist title/duration to DB for the UI.
        conn = await database.get_conn()
        try:
            await conn.execute(
                "UPDATE jobs SET title=?, duration=? WHERE job_id=?",
                (meta.title, meta.duration, job_id),
            )
            await conn.commit()
        finally:
            await conn.close()

    # ----- Stage: extracting_audio -----
    if not paths.audio_path.exists():
        await update("extracting_audio", 15, "extracting_audio")
        ffmpeg.extract_audio(paths.video_path, paths.audio_path)

    # ----- Stage: transcribing -----
    transcript = load_transcript_or_none(paths)
    if transcript is None:
        await update("transcribing", 25, "transcribing")
        transcript = transcription.transcribe(
            paths.audio_path, source_lang=source_lang
        )
        transcription.save_transcript(transcript, paths.transcript_path)
        # Persist detected source language.
        if transcript.language:
            conn = await database.get_conn()
            try:
                await conn.execute(
                    "UPDATE jobs SET source_lang=? WHERE job_id=?",
                    (transcript.language, job_id),
                )
                await conn.commit()
            finally:
                await conn.close()

    # ----- Stage: translating -----
    translation_obj = load_translation_or_none(paths)
    if translation_obj is None:
        await update("translating", 50, "translating")
        translation_obj = translation.translate(transcript, target_lang)
        translation.save_translation(translation_obj, paths.translation_path)

    # ----- Stage: generating_voice + synchronizing -----
    if not paths.timing_path.exists():
        await update("generating_voice", 65, "generating_voice")
        # Resolve voice.
        if not tts_voice:
            from app.services.tts import registry

            prov = registry.get(tts_provider)
            tts_voice = prov.default_voice(target_lang)
            conn = await database.get_conn()
            try:
                await conn.execute(
                    "UPDATE jobs SET tts_voice=? WHERE job_id=?",
                    (tts_voice, job_id),
                )
                await conn.commit()
            finally:
                await conn.close()
        await update("synchronizing", 75, "synchronizing")
        total_duration = float(transcript.duration or 0.0) or \
            ffmpeg.probe_duration(paths.video_path)
        synchronize(translation_obj, tts_provider, tts_voice, paths, total_duration)

    # ----- Stage: rendering -----
    final_audio = paths.audio / "timeline_final.wav"
    if not paths.output_path.exists():
        await update("rendering", 85, "rendering")
        # Mix original + dub if requested.
        if keep_original:
            mixed = paths.mixed_audio_path
            ffmpeg.mix_audio(
                paths.audio_path,
                final_audio,
                mixed,
                keep_original=True,
                original_volume=orig_vol,
                dub_volume=dub_vol,
            )
            dub_for_mux = mixed
        else:
            dub_for_mux = final_audio
        ffmpeg.mux_video_audio(
            paths.video_path,
            dub_for_mux,
            paths.output_path,
            crf=settings.output_crf,
        )

    await update("completed", 100, "completed")
    log.info("Job %s completed -> %s", job_id, paths.output_path)
