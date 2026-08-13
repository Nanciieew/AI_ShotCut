"""
Task routes.

GET  /api/v1/tasks/{task_id}         — Query task status
POST /api/v1/tasks/{task_id}/retry   — Retry failed task
"""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from apps.api.dependencies import get_db
from apps.api.routes.videos import _executor, _task_svc
from apps.api.services.artifact_service import ArtifactService
from apps.api.services.workflow_service import WorkflowService
from core.database.models import Task as TaskModel
from core.database.models import Video as VideoModel
from core.database.session_sync import get_sync_session
from core.task_storage import storage_service

router = APIRouter(tags=["tasks"])


@router.get("/tasks/{task_id}")
async def get_task(task_id: str, db: AsyncSession = Depends(get_db)):
    result = await _task_svc.get_task_status(task_id, db)
    if result["status"] == "NOT_FOUND":
        raise HTTPException(404, f"Task {task_id} not found")
    return result


@router.post("/tasks/{task_id}/retry")
async def retry_task(task_id: str, db: AsyncSession = Depends(get_db)):
    """Retry a FAILED or INTERRUPTED task.

    Creates a replacement Task with a new task_id, so the failed attempt and all
    of its Artifacts remain immutable.
    Only works for tasks marked as retryable or interrupted.
    """
    r = await db.execute(select(TaskModel).where(TaskModel.task_id == task_id))
    task = r.scalar_one_or_none()
    if task is None:
        raise HTTPException(404, f"Task {task_id} not found")

    if task.status not in ("FAILED", "INTERRUPTED"):
        raise HTTPException(409, f"Task is {task.status}, not retryable")

    # Verify artifacts still exist
    video = None
    r2 = await db.execute(select(VideoModel).where(VideoModel.video_id == task.video_id))
    video = r2.scalar_one_or_none()
    if video is None:
        raise HTTPException(404, "Associated video not found")

    # Keep the failed Task immutable and create a new task-scoped attempt.
    retry_count = (task.retry_count or 0) + 1
    with get_sync_session() as session:
        t = session.get(TaskModel, task_id)
        if t:
            t.retry_count = retry_count
            session.commit()

    replacement = _task_svc.create_task(
        project_id=video.project_id,
        video_id=task.video_id,
        parameters=task.parameters_json or {},
        retry_of_task_id=task_id,
        retry_count=retry_count,
    )

    # Submit the replacement via executor.
    artifact_svc = ArtifactService(storage_service)
    wf = WorkflowService(artifact_svc)
    workflow_parameters = task.parameters_json or {}
    _executor.submit(
        replacement["task_id"],
        wf.run_pipeline,
        project_id=video.project_id,
        task_id=replacement["task_id"],
        video_id=task.video_id,
        **workflow_parameters,
    )

    return {
        "task_id": replacement["task_id"],
        "retried_task_id": task_id,
        "status": "QUEUED",
        "retry_count": retry_count,
    }
