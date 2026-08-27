"""API route: video inspection (no download, just metadata)."""
from __future__ import annotations

from fastapi import APIRouter, HTTPException

from app.core.security import InvalidYouTubeURL
from app.models.job import VideoInfo, VideoInspectRequest
from app.services import youtube
from app.services.youtube import YouTubeError

router = APIRouter(prefix="/api/video", tags=["video"])


@router.post("/inspect", response_model=VideoInfo)
async def inspect_video(req: VideoInspectRequest) -> VideoInfo:
    try:
        meta = youtube.inspect(req.url)
    except InvalidYouTubeURL as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    except YouTubeError as exc:
        raise HTTPException(status_code=502, detail=str(exc))
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Inspect failed: {exc}")
    return VideoInfo(
        video_id=meta.video_id,
        title=meta.title,
        channel=meta.channel,
        duration=meta.duration,
        thumbnail=meta.thumbnail,
        available_qualities=meta.available_qualities,
        url=meta.url,
    )
