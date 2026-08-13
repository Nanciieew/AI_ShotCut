"""Artifact access routes.

GET /api/v1/artifacts/{artifact_id}/content?token=...  — signed download
GET /api/v1/tasks/{task_id}/artifacts                    — list artifacts per task
"""

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import FileResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from apps.api.dependencies import get_db
from core.database.models import Artifact, ModelRun, ModelRunOutput, Task
from core.security.artifact_tokens import verify_token
from core.task_storage import storage_service

router = APIRouter(tags=["artifacts"])


# ============================================================================
# Signed download
# ============================================================================


@router.get("/artifacts/{artifact_id}/content")
async def download_artifact(
    artifact_id: str,
    token: str = Query(..., description="HMAC-signed access token"),
    db: AsyncSession = Depends(get_db),
):
    """Download an artifact with a signed token.

    Token must be valid, unexpired, and match the artifact_id.
    purpose=download tokens require project permission (future).
    """
    payload = verify_token(token, allowed_purposes={"download", "provider"})
    if payload is None:
        raise HTTPException(403, "Invalid or expired token")
    if payload["artifact_id"] != artifact_id:
        raise HTTPException(403, "Token does not match artifact")

    purpose = payload["purpose"]

    # Look up artifact in DB
    r = await db.execute(select(Artifact).where(Artifact.artifact_id == artifact_id))
    art = r.scalar_one_or_none()
    if art is None:
        raise HTTPException(404, "Artifact not found")

    # Provider: restrict allowed types
    if purpose == "provider":
        allowed = {"audio.normalized"}
        if art.artifact_type not in allowed:
            raise HTTPException(403, f"Provider access denied for {art.artifact_type}")

    # Validate project_id matches
    if payload.get("project_id") and art.project_id != payload["project_id"]:
        raise HTTPException(403, "Token project_id mismatch")

    # Download: require project permission (placeholder for future auth)
    # Provider: no login cookie needed — HMAC is sufficient

    # Resolve URI to local path (only from DB, never from client)
    try:
        path = storage_service.resolve_local_path(art.uri)
    except ValueError:
        raise HTTPException(400, "Invalid artifact URI")

    if not path.is_file() or path.stat().st_size == 0:
        raise HTTPException(404, "Artifact file missing or empty")

    return FileResponse(str(path), media_type=art.mime_type or "application/octet-stream")


# ============================================================================
# Task-scoped artifact listing
# ============================================================================


@router.get("/tasks/{task_id}/final-result/download")
async def download_final_result(task_id: str, db: AsyncSession = Depends(get_db)):
    """Download the immutable FinalResult JSON generated for one Task."""
    task_result = await db.execute(select(Task).where(Task.task_id == task_id))
    task = task_result.scalar_one_or_none()
    if task is None:
        raise HTTPException(404, "Task not found")
    if task.status != "SUCCEEDED":
        raise HTTPException(409, f"Task is {task.status}; final result is unavailable")

    artifact_result = await db.execute(
        select(Artifact)
        .join(ModelRun, Artifact.producer_run_id == ModelRun.run_id)
        .where(
            ModelRun.task_id == task_id,
            Artifact.artifact_type == "final_scenes",
        )
        .order_by(Artifact.created_at.desc())
        .limit(1)
    )
    artifact = artifact_result.scalar_one_or_none()
    if artifact is None:
        raise HTTPException(404, "Final result Artifact not found")
    try:
        path = storage_service.resolve_local_path(artifact.uri)
    except ValueError as exc:
        raise HTTPException(400, "Invalid final result URI") from exc
    if not path.is_file() or path.stat().st_size == 0:
        raise HTTPException(404, "Final result file is missing")

    return FileResponse(
        str(path),
        media_type="application/json",
        filename=f"final_result_{task_id}.json",
    )


@router.get("/tasks/{task_id}/artifacts")
async def list_task_artifacts(task_id: str, db: AsyncSession = Depends(get_db)):
    """List all artifacts produced during this task.

    Query chain: Task → ModelRun → ModelRunOutput → Artifact.
    Does NOT return artifacts from other tasks of the same video.
    """
    r = await db.execute(
        select(Artifact)
        .join(ModelRunOutput, Artifact.artifact_id == ModelRunOutput.artifact_id)
        .join(ModelRun, ModelRunOutput.run_id == ModelRun.run_id)
        .where(ModelRun.task_id == task_id)
        .order_by(Artifact.created_at)
    )
    artifacts = r.scalars().all()

    return {
        "task_id": task_id,
        "artifacts": [
            {
                "artifact_id": a.artifact_id,
                "artifact_type": a.artifact_type,
                "uri": a.uri,
                "format": a.format,
                "size_bytes": a.size_bytes,
                "sha256": a.sha256,
                "created_at": a.created_at.isoformat() if a.created_at else None,
            }
            for a in artifacts
        ],
    }
