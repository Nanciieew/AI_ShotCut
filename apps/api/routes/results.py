"""
Result query routes.

GET /api/v1/videos/{video_id}/results — Get analysis results for a video
"""

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from apps.api.dependencies import get_db

router = APIRouter(tags=["results"])


@router.get("/videos/{video_id}/results")
async def get_results(
    video_id: str,
    db: AsyncSession = Depends(get_db),
):
    """Get the analysis results for a video.

    If the pipeline is still running, returns status PROCESSING.
    If complete, returns the result_uri pointing to final_result.json.
    """
    # TODO: Implement result query (MVP Phase 2)
    return {
        "status": "PROCESSING",
        "message": "placeholder — get_results not yet implemented",
    }
