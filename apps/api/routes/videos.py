"""
Video management routes.

POST   /api/v1/videos              — Upload a video
POST   /api/v1/videos/{id}/analysis — Start full analysis pipeline
GET    /api/v1/videos/{id}          — Get video metadata
"""

from fastapi import APIRouter, Depends, UploadFile, File
from sqlalchemy.ext.asyncio import AsyncSession

from apps.api.dependencies import get_db

router = APIRouter(tags=["videos"])


@router.post("/videos")
async def upload_video(
    file: UploadFile = File(...),
    db: AsyncSession = Depends(get_db),
):
    """Upload a video file for analysis.

    Returns a video_id to use in subsequent API calls.
    """
    # TODO: Implement video upload (MVP Phase 3)
    return {
        "video_id": "placeholder",
        "upload_status": "SUCCEEDED",
        "message": "placeholder — upload_video not yet implemented",
    }


@router.post("/videos/{video_id}/analysis")
async def start_analysis(
    video_id: str,
    db: AsyncSession = Depends(get_db),
):
    """Start the full video analysis pipeline.

    Returns a task_id for tracking progress.
    """
    # TODO: Implement pipeline trigger (MVP Phase 2)
    return {
        "task_id": "placeholder",
        "video_id": video_id,
        "status": "QUEUED",
        "message": "placeholder — start_analysis not yet implemented",
    }


@router.get("/videos/{video_id}")
async def get_video(
    video_id: str,
    db: AsyncSession = Depends(get_db),
):
    """Get video metadata."""
    # TODO: Implement video lookup (MVP Phase 3)
    return {
        "video_id": video_id,
        "message": "placeholder — get_video not yet implemented",
    }
