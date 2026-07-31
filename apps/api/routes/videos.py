"""
Video management routes.

POST   /api/v1/videos              — Upload a video
POST   /api/v1/videos/{id}/analyze-shots — Start shot analysis pipeline
GET    /api/v1/videos/{id}          — Get video metadata
"""

from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form
from sqlalchemy.ext.asyncio import AsyncSession

from apps.api.dependencies import get_db
from apps.api.services.analysis_service import submit_full_pipeline

router = APIRouter(tags=["videos"])


@router.post("/videos")
async def upload_video(
    file: UploadFile = File(...),
    project_id: str = Form(default="default"),
    db: AsyncSession = Depends(get_db),
):
    """Upload a video file and create DB records.

    Saves the video to local storage, creates Video + Artifact records,
    and returns a video_id for subsequent pipeline submission.
    """
    # TODO: Implement actual file save to storage (MVP Phase 3)
    # For now this is a placeholder — use the analyze-shots endpoint
    # which accepts a pre-staged video path.
    return {
        "video_id": "placeholder",
        "upload_status": "SUCCEEDED",
        "message": "upload_video not yet implemented — use POST /videos/{id}/analyze-shots with staged video",
    }


@router.post("/videos/{video_id}/analyze-shots")
async def start_shot_analysis(
    video_id: str,
    video_path: str = Form(..., description="Path to video file on storage"),
    project_id: str = Form(default="default"),
    db: AsyncSession = Depends(get_db),
):
    """Start the OmniShotCut shot detection pipeline.

    Pipeline: normalize_video → detect_shots

    The video must already be staged at the specified storage path.
    Returns a task_id for tracking progress via GET /api/v1/tasks/{task_id}.
    """
    result = await submit_full_pipeline(
        db=db,
        video_path=video_path,
        project_id=project_id,
    )
    return result


@router.get("/videos/{video_id}")
async def get_video(
    video_id: str,
    db: AsyncSession = Depends(get_db),
):
    """Get video metadata and analysis status."""
    from sqlalchemy import select
    from core.database.models import Video

    result = await db.execute(select(Video).where(Video.video_id == video_id))
    video = result.scalar_one_or_none()

    if video is None:
        raise HTTPException(status_code=404, detail=f"Video {video_id} not found")

    return {
        "video_id": video.video_id,
        "project_id": video.project_id,
        "source_uri": video.source_uri,
        "normalized_uri": video.normalized_uri,
        "duration_ms": video.duration_ms,
        "fps_num": video.fps_num,
        "fps_den": video.fps_den,
        "width": video.width,
        "height": video.height,
        "created_at": video.created_at.isoformat() if video.created_at else None,
    }
