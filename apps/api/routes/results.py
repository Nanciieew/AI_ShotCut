"""
Result query routes.

GET /api/v1/videos/{video_id}/results — Get analysis results for a video
"""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from apps.api.dependencies import get_db
from apps.api.routes.videos import _task_svc

router = APIRouter(tags=["results"])


@router.get("/videos/{video_id}/results")
async def get_results(
    video_id: str,
    db: AsyncSession = Depends(get_db),
):
    """Get the full analysis results for a video.

    Returns video metadata, shot list, artifact references, and
    current pipeline status. If still running, status reflects progress.
    """
    result = await _task_svc.get_video_results(video_id, db)
    if result.get("status") == "NOT_FOUND":
        raise HTTPException(status_code=404, detail=f"Video {video_id} not found")
    return result
