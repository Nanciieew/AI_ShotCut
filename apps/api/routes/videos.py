"""Video + Task routes — /api/v1/ per §4.

POST   /api/v1/projects/{project_id}/videos          — Upload video
POST   /api/v1/videos/{video_id}/tasks               — Create analysis task
GET    /api/v1/videos/{video_id}                      — Get video metadata
GET    /api/v1/tasks/{task_id}                        — Get task status
GET    /api/v1/videos/{video_id}/results              — Get results
"""

import hashlib
import json
import os
import re
import uuid
from pathlib import Path

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from fastapi.responses import FileResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from apps.api.dependencies import get_db
from apps.api.services.artifact_service import ArtifactService
from apps.api.services.task_service import TaskService
from core.config import get_settings
from core.database.models import Artifact, ModelRun, Task
from core.database.models import Video as VideoModel
from core.database.repositories import VideoRepository
from core.database.session_sync import get_sync_session
from core.task_storage import storage_service
from schemas.task import AnalysisTaskRequest

router = APIRouter(tags=["videos"])

from apps.api.services.executor import BackgroundExecutor

_artifact_svc = ArtifactService(storage_service)
_task_svc = TaskService()
_executor = BackgroundExecutor(max_workers=2)

# UUID pattern for route validation
_UUID_RE = re.compile(r"^[a-f0-9]{32}$")


def _new_id() -> str:
    return uuid.uuid4().hex


def _container_extension(container_format: str) -> str | None:
    """Map FFprobe format_name to the canonical stored extension."""
    formats = {item.strip().lower() for item in container_format.split(",")}
    if formats.intersection({"mov", "mp4", "m4a", "3gp", "3g2", "mj2"}):
        return "mp4"
    if formats.intersection({"matroska", "webm"}):
        return "mkv"
    if "avi" in formats:
        return "avi"
    return None


# ============================================================================
# Upload
# ============================================================================


@router.get("/upload-config")
async def get_upload_config():
    """Return the constrained upload contract for the web client."""
    settings = get_settings()
    return {
        "project_id": settings.default_project_id,
        "allowed_containers": settings.upload_allowed_containers,
        "max_bytes": settings.upload_max_bytes,
        "storage_template": "storage://projects/{project_id}/videos/{video_id}/source/{filename}",
        "recommended_max_height": 720,
    }


@router.post("/projects/{project_id}/videos")
async def upload_video(
    project_id: str,
    file: UploadFile = File(...),
    db: AsyncSession = Depends(get_db),
):
    """Upload a video, create project+video records. Returns video_id."""
    if not _UUID_RE.match(project_id):
        raise HTTPException(422, f"Invalid project_id format: {project_id!r}")

    video_id = _new_id()
    filename = file.filename or "untitled.mp4"
    safe_name = re.sub(r"[^a-zA-Z0-9._-]", "_", filename)

    # Stream upload to temp file — compute SHA-256, check size
    settings = get_settings()
    max_bytes = settings.upload_max_bytes

    source_dir = storage_service.source_dir(project_id, video_id)
    os.makedirs(source_dir, exist_ok=True)
    tmp_path = os.path.join(source_dir, safe_name + ".tmp")

    h = hashlib.sha256()
    size = 0
    try:
        with open(tmp_path, "wb") as f:
            while True:
                chunk = await file.read(65536)
                if not chunk:
                    break
                size += len(chunk)
                if size > max_bytes:
                    f.close()
                    os.unlink(tmp_path)
                    raise HTTPException(413, f"File exceeds {max_bytes} bytes")
                h.update(chunk)
                f.write(chunk)
    except HTTPException:
        raise
    except Exception:
        if os.path.exists(tmp_path):
            os.unlink(tmp_path)
        raise HTTPException(500, "Upload failed")

    sha256_digest = h.hexdigest()

    # FFprobe: detect real container, reject fake extensions
    from core.media.ffprobe import run_ffprobe

    try:
        probe = run_ffprobe(tmp_path)
    except Exception:
        os.unlink(tmp_path)
        raise HTTPException(400, "File is not a valid video")

    real_container = probe.container_format or "unknown"
    # Determine extension from real container
    container_ext = _container_extension(real_container)
    if container_ext is None:
        os.unlink(tmp_path)
        raise HTTPException(400, f"Unsupported container: {real_container}")
    if container_ext not in settings.upload_allowed_containers:
        os.unlink(tmp_path)
        raise HTTPException(400, f"Container {real_container} not in allow list")

    # Use true extension
    final_name = (Path(safe_name).stem or "untitled") + "." + container_ext
    dest_path = os.path.join(source_dir, final_name)

    # Atomic rename
    try:
        os.replace(tmp_path, dest_path)
    except Exception:
        os.unlink(tmp_path)
        raise HTTPException(500, "Upload failed — cannot move file")

    source_uri = f"storage://projects/{project_id}/videos/{video_id}/source/{final_name}"

    # Create DB records only after successful file write
    with get_sync_session() as session:
        repo = VideoRepository(session)
        repo.ensure_project(project_id)
        repo.create(video_id=video_id, project_id=project_id, source_uri=source_uri)
        session.commit()

    return {
        "video_id": video_id,
        "project_id": project_id,
        "filename": final_name,
        "source_uri": source_uri,
        "sha256": sha256_digest,
        "container": real_container,
        "size_bytes": size,
        "upload_status": "SUCCEEDED",
    }


# ============================================================================
# Create Task
# ============================================================================


@router.post("/videos/{video_id}/tasks")
async def create_analysis_task(
    video_id: str,
    parameters: AnalysisTaskRequest,
    db: AsyncSession = Depends(get_db),
):
    """Create a new analysis task for an existing video. Returns 202."""
    r = await db.execute(select(VideoModel).where(VideoModel.video_id == video_id))
    video = r.scalar_one_or_none()
    if video is None:
        raise HTTPException(404, f"Video {video_id} not found")

    from apps.api.services.workflow_service import WorkflowService

    workflow_parameters = parameters.model_dump()
    task = _task_svc.create_task(
        project_id=video.project_id,
        video_id=video_id,
        parameters=workflow_parameters,
    )

    # Start Workflow via controlled executor
    wf = WorkflowService(_artifact_svc)
    _executor.submit(
        task["task_id"],
        wf.run_pipeline,
        project_id=video.project_id,
        task_id=task["task_id"],
        video_id=video_id,
        **workflow_parameters,
    )

    return {
        "task_id": task["task_id"],
        "video_id": task["video_id"],
        "project_id": task["project_id"],
        "status": "QUEUED",
        "stage": "created",
        "progress": 0,
    }


# ============================================================================
# Queries
# ============================================================================


@router.get("/videos/{video_id}")
async def get_video(video_id: str, db: AsyncSession = Depends(get_db)):
    r = await db.execute(select(VideoModel).where(VideoModel.video_id == video_id))
    video = r.scalar_one_or_none()
    if video is None:
        raise HTTPException(404, f"Video {video_id} not found")
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
    }


@router.get("/videos/{video_id}/keyframes/{shot_id}/{image_slot}")
async def get_shot_keyframe(
    video_id: str,
    shot_id: str,
    image_slot: str,
    db: AsyncSession = Depends(get_db),
):
    """Return a keyframe resolved through the latest successful task Artifact."""
    if not _UUID_RE.match(video_id) or not _UUID_RE.match(shot_id):
        raise HTTPException(422, "Invalid video_id or shot_id")
    position_by_slot = {
        "img_1": (1, 4),
        "img_2": (1, 2),
        "img_3": (3, 4),
    }
    position = position_by_slot.get(image_slot)
    if position is None:
        raise HTTPException(422, "image_slot must be img_1, img_2, or img_3")

    result = await db.execute(
        select(Artifact)
        .join(ModelRun, Artifact.producer_run_id == ModelRun.run_id)
        .join(Task, ModelRun.task_id == Task.task_id)
        .where(
            Artifact.video_id == video_id,
            Artifact.artifact_type == "shot_keyframes",
            ModelRun.status == "SUCCEEDED",
            Task.status == "SUCCEEDED",
        )
        .order_by(ModelRun.started_at.desc())
        .limit(1)
    )
    summary_artifact = result.scalar_one_or_none()
    if summary_artifact is None:
        raise HTTPException(404, "No successful keyframe Artifact found")

    try:
        summary_path = storage_service.resolve_local_path(summary_artifact.uri)
        summary = json.loads(summary_path.read_text(encoding="utf-8"))
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        raise HTTPException(500, "Keyframe Artifact is unreadable") from exc

    shot = next(
        (item for item in summary.get("shots", []) if item.get("shot_id") == shot_id),
        None,
    )
    if shot is None:
        raise HTTPException(404, "Shot keyframes not found")
    sample = next(
        (
            item
            for item in shot.get("samples", [])
            if (item.get("position_num"), item.get("position_den")) == position and item.get("uri")
        ),
        None,
    )
    if sample is None:
        raise HTTPException(404, f"{image_slot} is not available for this shot")
    try:
        image_path = storage_service.resolve_local_path(sample["uri"])
    except ValueError as exc:
        raise HTTPException(500, "Invalid keyframe URI") from exc
    if not image_path.is_file() or image_path.stat().st_size == 0:
        raise HTTPException(404, "Keyframe file missing")
    return FileResponse(str(image_path), media_type="image/jpeg")
