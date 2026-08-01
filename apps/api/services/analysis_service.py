"""Analysis orchestration service — submits Celery chains for video analysis.

Handles:
  - Creating Project/Video/Task records
  - Delegating to core.orchestration for Celery chain construction
  - Validating preconditions

Per CLAUDE.md §2.1, this service MUST NOT directly define task execution order.
It delegates to core.orchestration canvas builders instead.
"""

import uuid

from core.orchestration import build_omnishotcut_canvas


def _new_id() -> str:
    return uuid.uuid4().hex[:16]


async def submit_full_pipeline(
    db,
    video_path: str,
    project_id: str | None = None,
    extract_keyframes: bool = False,
) -> dict:
    """Create DB records and submit the analysis pipeline chain.

    Parameters
    ----------
    db : AsyncSession
        Database session (async).
    video_path : str
        Path to the source video file.
    project_id : Optional[str]
        Project identifier (default: "default").
    extract_keyframes : bool
        When True, include the keyframe extraction step after shot detection.
        Default False.

    Returns
    -------
    dict
        {task_id, video_id, project_id, status, stage, message}
    """
    from core.database.repositories import (
        TaskRepository,
        VideoRepository,
    )
    from core.database.session_sync import get_sync_session

    vid = _new_id()
    task_id = _new_id()
    proj_id = project_id or "default"

    with get_sync_session() as session:
        video_repo = VideoRepository(session)
        task_repo = TaskRepository(session)

        # Ensure project exists
        video_repo.ensure_project(proj_id, name=proj_id)

        # Create video record + original artifact
        source_uri = f"storage://projects/{proj_id}/videos/{vid}/source/{video_path}"
        video = video_repo.create(
            video_id=vid,
            project_id=proj_id,
            source_uri=source_uri,
        )

        # Create task
        task = task_repo.create(
            task_id=task_id,
            video_id=vid,
            task_type="omnishotcut_pipeline",
        )
        session.commit()

    # Build and submit Celery chain via orchestration layer
    try:
        canvas = build_omnishotcut_canvas(
            task_id=task_id,
            video_id=vid,
            extract_keyframes=extract_keyframes,
        )
        result = canvas.apply_async()
        celery_task_id = result.id

        # Update celery_task_id
        with get_sync_session() as session:
            task_repo = TaskRepository(session)
            task_repo.set_celery_id(task_id, celery_task_id)
            session.commit()
    except Exception as e:
        with get_sync_session() as session:
            task_repo = TaskRepository(session)
            task_repo.set_error(task_id, "CELERY_DISPATCH_FAILED", str(e))
            session.commit()
        return {
            "task_id": task_id,
            "video_id": vid,
            "project_id": proj_id,
            "status": "FAILED",
            "stage": "dispatch",
            "error": {"code": "CELERY_DISPATCH_FAILED", "message": str(e)},
        }

    steps_msg = "normalize_video → detect_shots"
    if extract_keyframes:
        steps_msg += " → extract_keyframes"
    steps_msg += " → pipeline_complete"

    return {
        "task_id": task_id,
        "video_id": vid,
        "project_id": proj_id,
        "status": "QUEUED",
        "stage": "normalize_video",
        "progress": 0,
        "celery_task_id": celery_task_id,
        "message": f"Pipeline submitted: {steps_msg}",
    }


async def get_task_status(task_id: str, db) -> dict:
    """Query task status from the database."""
    from sqlalchemy import select

    from core.database.models import Task

    result = await db.execute(select(Task).where(Task.task_id == task_id))
    task = result.scalar_one_or_none()

    if task is None:
        return {
            "task_id": task_id,
            "status": "NOT_FOUND",
            "message": f"Task {task_id} not found",
        }

    return {
        "task_id": task.task_id,
        "video_id": task.video_id,
        "task_type": task.task_type,
        "status": task.status,
        "stage": task.stage,
        "progress": task.progress,
        "created_at": task.created_at.isoformat() if task.created_at else None,
        "started_at": task.started_at.isoformat() if task.started_at else None,
        "finished_at": task.finished_at.isoformat() if task.finished_at else None,
        "error_code": task.error_code,
        "error_message": task.error_message,
        "celery_task_id": task.celery_task_id,
    }


async def get_video_results(video_id: str, db) -> dict:
    """Get all results + artifacts for a video."""
    from sqlalchemy import select

    from core.database.models import Artifact, Shot, Task, Video

    # Video
    result = await db.execute(select(Video).where(Video.video_id == video_id))
    video = result.scalar_one_or_none()
    if video is None:
        return {"video_id": video_id, "status": "NOT_FOUND"}

    # Shots
    result = await db.execute(select(Shot).where(Shot.video_id == video_id).order_by(Shot.index))
    shots = result.scalars().all()

    # Artifacts
    result = await db.execute(select(Artifact).where(Artifact.video_id == video_id))
    artifacts = result.scalars().all()

    # Latest task
    result = await db.execute(
        select(Task).where(Task.video_id == video_id).order_by(Task.created_at.desc()).limit(1)
    )
    task = result.scalar_one_or_none()

    return {
        "video_id": video_id,
        "project_id": video.project_id,
        "source_uri": video.source_uri,
        "normalized_uri": video.normalized_uri,
        "duration_ms": video.duration_ms,
        "fps_num": video.fps_num,
        "fps_den": video.fps_den,
        "width": video.width,
        "height": video.height,
        "task": {
            "task_id": task.task_id if task else None,
            "status": task.status if task else None,
            "stage": task.stage if task else None,
            "progress": task.progress if task else 0,
        }
        if task
        else None,
        "shots": [
            {
                "shot_id": s.shot_id,
                "index": s.index,
                "start_ms": s.start_ms,
                "end_ms": s.end_ms,
                "boundary_type": s.boundary_type,
                "confidence": s.confidence,
            }
            for s in shots
        ],
        "artifacts": [
            {
                "artifact_id": a.artifact_id,
                "artifact_type": a.artifact_type,
                "uri": a.uri,
                "format": a.format,
                "sha256": a.sha256,
            }
            for a in artifacts
        ],
    }
