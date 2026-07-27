"""
Task query routes.

GET /api/v1/tasks/{task_id} — Query task status and progress
"""

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from apps.api.dependencies import get_db

router = APIRouter(tags=["tasks"])


@router.get("/tasks/{task_id}")
async def get_task(
    task_id: str,
    db: AsyncSession = Depends(get_db),
):
    """Query the status and progress of an async pipeline task."""
    # TODO: Implement task status query (MVP Phase 2)
    return {
        "task_id": task_id,
        "status": "PENDING",
        "stage": None,
        "progress": 0,
        "message": "placeholder — get_task not yet implemented",
    }
