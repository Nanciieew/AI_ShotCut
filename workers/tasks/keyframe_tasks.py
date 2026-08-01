"""
Celery task for keyframe extraction.

Runs after shot.detect in the pipeline chain. Extracts 3 keyframes
(25%, 50%, 75%) per shot from the normalized video via PyAV single-pass
sequential decode.

Task name: video.extract_keyframes
Queue: video (CPU — PyAV, JPEG encode, disk I/O)
"""

import json
import os
import time
import uuid
from datetime import datetime, timezone

from core.database.models import ModelRun
from core.database.repositories import (
    ArtifactRepository,
    TaskRepository,
    VideoRepository,
)
from core.database.session_sync import get_sync_session
from core.logging.context import clear_task_context, set_task_context
from core.media.exceptions import KeyframeExtractionError, NonRetryableTaskError
from workers.celery_app import app

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _resolve_uri(uri: str, storage_root: str) -> str:
    """Convert storage:// URI to local absolute path."""
    prefix = "storage://"
    if uri.startswith(prefix):
        return os.path.join(storage_root, uri[len(prefix) :])
    return uri


# ---------------------------------------------------------------------------
# Task
# ---------------------------------------------------------------------------


@app.task(name="video.extract_keyframes", bind=True, max_retries=1)
def extract_keyframes(self, task_id: str, video_id: str) -> dict:
    """Extract keyframes from the normalized video for every detected shot.

    Resolves its own inputs from the database via task_id — does NOT
    rely on chain result passing (all chain links are immutable).

    Parameters
    ----------
    task_id : str
        App-level task identifier.
    video_id : str
        Video to process.

    Returns
    -------
    dict
        IO_Rule §2-shaped result with artifacts.keyframes URI.
    """
    set_task_context(task_id=task_id, video_id=video_id, model="ffmpeg_keyframes")

    storage_root = os.getenv("STORAGE_ROOT", "./data")

    # --- 1. Guard: task not already FAILED ---
    with get_sync_session() as session:
        task = TaskRepository(session).get(task_id)
        if task and task.status == "FAILED":
            clear_task_context()
            raise NonRetryableTaskError(
                f"[TASK_ALREADY_FAILED] Task {task_id} is already FAILED — "
                f"skipping keyframe extraction"
            )

    # --- 2. Load video + shots artifact ---
    with get_sync_session() as session:
        video_repo = VideoRepository(session)
        artifact_repo = ArtifactRepository(session)

        video = video_repo.get(video_id)
        if video is None:
            clear_task_context()
            raise NonRetryableTaskError(f"[VIDEO_NOT_FOUND] Video {video_id} not in DB")

        normalized_uri = video.normalized_uri
        if not normalized_uri:
            clear_task_context()
            raise NonRetryableTaskError(
                "[NOT_NORMALIZED] Video has no normalized_uri. Run normalize_video first."
            )

        video_path = _resolve_uri(normalized_uri, storage_root)
        if not os.path.exists(video_path):
            clear_task_context()
            raise NonRetryableTaskError(f"[FILE_NOT_FOUND] Normalized video missing: {video_path}")

        # Resolve shots artifact by task_id (same pipeline run)
        shots_artifact = artifact_repo.get_artifact_for_task(
            task_id=task_id,
            video_id=video_id,
            artifact_type="shots",
            model_name="omnishotcut",
        )
        if shots_artifact is None:
            clear_task_context()
            raise NonRetryableTaskError(
                "[SHOTS_NOT_FOUND] No shots artifact found for this task. "
                "Ensure shot.detect completed successfully."
            )

        shots_uri = shots_artifact.uri
        shots_path = _resolve_uri(shots_uri, storage_root)
        if not os.path.exists(shots_path):
            clear_task_context()
            raise NonRetryableTaskError(
                f"[SHOTS_FILE_MISSING] Shots artifact file not found: {shots_path}"
            )

        # Get normalized video artifact for lineage
        norm_artifact = artifact_repo.get_artifact_for_task(
            task_id=task_id,
            video_id=video_id,
            artifact_type="normalized_video",
            model_name="ffmpeg_normalizer",
        )

    # --- 3. Load shots data ---
    try:
        with open(shots_path, encoding="utf-8") as f:
            shots_data = json.load(f)
    except (json.JSONDecodeError, OSError) as e:
        clear_task_context()
        raise NonRetryableTaskError(f"[SHOTS_READ_FAILED] {e}")

    # --- 4. Create ModelRun ---
    run_id = uuid.uuid4().hex[:16]
    with get_sync_session() as session:
        task_repo = TaskRepository(session)
        task_repo.update_progress(task_id, 72, stage="extract_keyframes")

        model_run = ModelRun(
            run_id=run_id,
            task_id=task_id,
            video_id=video_id,
            model_name="ffmpeg_keyframes",
            model_version="1.0.0",
            schema_version="1.0",
            status="RUNNING",
            device="cpu",
            started_at=datetime.now(timezone.utc),
        )
        session.add(model_run)
        session.commit()

    # --- 5. Get video frame metadata ---
    fps_num = video.fps_num or 0
    fps_den = video.fps_den or 1
    frame_count = getattr(video, "frame_count", 0) or 0
    video_width = video.width or 0
    video_height = video.height or 0

    if fps_num <= 0 or fps_den <= 0:
        # Fallback: probe the video
        from core.media.ffprobe import run_ffprobe

        try:
            probe = run_ffprobe(str(video_path))
            fps_num = probe.fps_num
            fps_den = probe.fps_den
            frame_count = probe.frame_count
            video_width = probe.width
            video_height = probe.height
        except Exception:
            clear_task_context()
            raise NonRetryableTaskError("[NO_FPS] Cannot determine FPS from DB or probe")

    # --- 6. Load config ---
    from core.config import get_settings

    settings = get_settings()

    # --- 7. Run extraction ---
    from pipelines.services.keyframe_service import run_keyframe_extraction

    t0 = time.monotonic()
    try:
        service_result = run_keyframe_extraction(
            video_path=video_path,
            shots_data=shots_data,
            fps_num=fps_num,
            fps_den=fps_den,
            frame_count=frame_count,
            video_width=video_width,
            video_height=video_height,
            shots_artifact_id=shots_artifact.artifact_id,
            normalized_video_artifact_id=(norm_artifact.artifact_id if norm_artifact else ""),
            video_id=video_id,
            run_id=run_id,
            output_root=storage_root,
            image_format=settings.keyframe_format,
            quality=settings.keyframe_quality,
            max_long_side=settings.keyframe_max_long_side,
        )
    except KeyframeExtractionError as e:
        with get_sync_session() as session:
            task_repo = TaskRepository(session)
            task_repo.set_error(task_id, "KEYFRAME_EXTRACTION_FAILED", str(e))
            mr = session.get(ModelRun, run_id)
            if mr:
                mr.status = "FAILED"
                mr.finished_at = datetime.now(timezone.utc)
            session.commit()
        clear_task_context()
        raise NonRetryableTaskError(f"[KEYFRAME_EXTRACTION_FAILED] {e}")
    except Exception as e:
        with get_sync_session() as session:
            task_repo = TaskRepository(session)
            task_repo.set_error(task_id, "KEYFRAME_EXTRACTION_FAILED", str(e))
            mr = session.get(ModelRun, run_id)
            if mr:
                mr.status = "FAILED"
                mr.finished_at = datetime.now(timezone.utc)
            session.commit()
        clear_task_context()
        raise NonRetryableTaskError(f"[KEYFRAME_EXTRACTION_FAILED] {e}")

    runtime_ms = int((time.monotonic() - t0) * 1000)

    if service_result.status == "FAILED":
        with get_sync_session() as session:
            task_repo = TaskRepository(session)
            task_repo.set_error(
                task_id,
                service_result.error_code,
                service_result.error_message,
            )
            mr = session.get(ModelRun, run_id)
            if mr:
                mr.status = "FAILED"
                mr.finished_at = datetime.now(timezone.utc)
            session.commit()
        clear_task_context()
        raise NonRetryableTaskError(f"[{service_result.error_code}] {service_result.error_message}")

    # --- 8. Create Artifact DB record + finalize ---
    with get_sync_session() as session:
        task_repo = TaskRepository(session)
        artifact_repo = ArtifactRepository(session)

        artifact_repo.create(
            artifact_id=service_result.summary_artifact_id,
            video_id=video_id,
            run_id=run_id,
            artifact_type="shot_keyframes",
            uri=service_result.summary_artifact_uri,
            format="json",
            schema_version="1.0",
            sha256=service_result.summary_sha256,
        )

        # Update ModelRun → SUCCEEDED
        mr = session.get(ModelRun, run_id)
        if mr:
            mr.status = "SUCCEEDED"
            mr.runtime_ms = runtime_ms
            mr.finished_at = datetime.now(timezone.utc)

        # Update task progress — DO NOT mark SUCCEEDED
        # (only final.pipeline_complete does that)
        task_repo.update_progress(task_id, 95, stage="extract_keyframes")
        session.commit()

    clear_task_context()

    return {
        "task_id": task_id,
        "video_id": video_id,
        "run_id": run_id,
        "status": "SUCCEEDED",
        "stage": "extract_keyframes",
        "model": {"name": "ffmpeg_keyframes", "version": "1.0.0"},
        "artifacts": {
            "keyframes": service_result.summary_artifact_uri,
        },
        "metrics": {
            "shot_count": service_result.shot_count,
            "unique_image_count": service_result.unique_image_count,
            "deduplicated_count": service_result.deduplicated_count,
            "total_bytes": service_result.total_bytes,
            "runtime_ms": runtime_ms,
        },
    }
