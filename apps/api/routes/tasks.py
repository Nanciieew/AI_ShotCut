"""
Task query routes.

GET  /api/v1/tasks/{task_id}  — Query task status and progress
POST /api/v1/tasks/{task_id}/retry — Retry a failed task
"""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from apps.api.dependencies import get_db
from apps.api.services.analysis_service import get_task_status

router = APIRouter(tags=["tasks"])


@router.get("/tasks/{task_id}")
async def get_task(
    task_id: str,
    db: AsyncSession = Depends(get_db),
):
    """Query the status and progress of an async pipeline task.

    Returns current status, stage, progress (0-100), and error info if failed.
    """
    result = await get_task_status(task_id, db)
    if result["status"] == "NOT_FOUND":
        raise HTTPException(status_code=404, detail=f"Task {task_id} not found")
    return result
