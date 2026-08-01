"""
Celery tasks for video preprocessing.

Handles:
  - Video normalization (FFmpeg re-encode via core.media)
  - Metadata extraction (ffprobe via core.media)
  - probe_before.json / probe_after.json preservation
  - Normalization validation
  - Artifact generation (normalized.mp4 + manifest)
"""

import os
import time
import uuid
from datetime import datetime, timezone

from core.artifacts import ArtifactProducer
from core.artifacts.writer import ArtifactWriter
from core.database.models import ModelRun
from core.database.repositories import (
    ArtifactRepository,
    TaskRepository,
    VideoRepository,
)
from core.database.session_sync import get_sync_session
from core.logging.context import clear_task_context, set_task_context
from core.media.exceptions import FFmpegError, FFprobeError
from core.media.ffmpeg import build_normalize_command, get_ffmpeg_version, run_ffmpeg
from core.media.ffprobe import probe_video
from core.media.normalization import validate_normalization
from core.media.schemas import NormalizationConfig
from workers.celery_app import app

# ---------------------------------------------------------------------------
# Task
# ---------------------------------------------------------------------------


@app.task(name="video.normalize", bind=True, max_retries=3)
def normalize_video(self, task_id: str, video_id: str) -> dict:
    """Normalize an uploaded video to the project standard format.

    Per spec: FFmpeg标准化_OmniShotCut_Docker_Celery单模型闭环.md §10

    Input: {task_id, video_id}
    Output: {task_id, video_id, normalized_artifact_id,
             normalized_artifact_uri, status}

    Steps:
      1. Query Video / Task / Input Artifact from DB
      2. Update Task stage → normalize_video, status → RUNNING
      3. FFprobe input → save probe_before.json
      4. FFmpeg normalize → normalized.mp4 (temp → atomic rename)
      5. FFprobe output → save probe_after.json
      6. Validate normalization result
      7. Write Manifest
      8. Compute SHA256
      9. Create normalized_video Artifact in DB
     10. Update Task stage + Video metadata
     11. Return minimal result (no binary data)
    """
    set_task_context(task_id=task_id, video_id=video_id, model="ffmpeg")

    storage_root = os.getenv("STORAGE_ROOT", "./data")
    writer = ArtifactWriter(storage_root)

    with get_sync_session() as session:
        task_repo = TaskRepository(session)
        video_repo = VideoRepository(session)

        # --- 1. Load video record ---
        video = video_repo.get(video_id)
        if video is None:
            clear_task_context()
            return _fail(task_id, video_id, "VIDEO_NOT_FOUND", f"Video {video_id} not in DB")

        source_uri = video.source_uri
        if not source_uri:
            clear_task_context()
            return _fail(task_id, video_id, "NO_SOURCE_URI", "Video has no source_uri")

        source_path = _resolve_uri(source_uri, storage_root)
        if not os.path.exists(source_path):
            clear_task_context()
            return _fail(task_id, video_id, "SOURCE_NOT_FOUND", f"File not found: {source_path}")

        # --- 2. Update task → RUNNING ---
        task_repo.update_status(task_id, "RUNNING")
        task_repo.update_progress(task_id, 10, stage="normalize_video")

        # Create ModelRun record
        run_id = uuid.uuid4().hex[:16]
        model_run = ModelRun(
            run_id=run_id,
            task_id=task_id,
            video_id=video_id,
            model_name="ffmpeg_normalizer",
            model_version="1.0.0",
            schema_version="1.0",
            status="RUNNING",
            device="cpu",
            started_at=datetime.now(timezone.utc),
        )
        session.add(model_run)
        session.commit()

    # --- 3. Derive output paths ---
    project_id = video.project_id if video else "default"
    norm_version = "1.0.0"
    artifact_base = (
        f"projects/{project_id}/videos/{video_id}/artifacts/video_normalization/{norm_version}"
    )
    norm_dir_abs = os.path.join(storage_root, artifact_base)
    os.makedirs(norm_dir_abs, exist_ok=True)

    normalized_rel = f"{artifact_base}/normalized.mp4"
    normalized_abs = os.path.join(storage_root, normalized_rel)
    probe_before_rel = f"{artifact_base}/probe_before.json"
    probe_before_abs = os.path.join(storage_root, probe_before_rel)
    probe_after_rel = f"{artifact_base}/probe_after.json"
    probe_after_abs = os.path.join(storage_root, probe_after_rel)

    # --- 4. FFprobe input → probe_before.json ---
    with get_sync_session() as session:
        task_repo = TaskRepository(session)
        task_repo.update_progress(task_id, 15, stage="normalize_video")
        session.commit()

    try:
        probe_before = probe_video(
            source_path,
            output_dir=norm_dir_abs,
            label="probe_before",
        )
    except FFprobeError as e:
        with get_sync_session() as session:
            TaskRepository(session).set_error(task_id, "VIDEO_PROBE_FAILED", str(e))
            session.commit()
        clear_task_context()
        return _fail(task_id, video_id, "VIDEO_PROBE_FAILED", str(e))

    # Save probe_before as artifact file
    _write_json_atomic(probe_before_abs, probe_before.to_dict())

    # --- 5. FFmpeg normalize ---
    with get_sync_session() as session:
        task_repo = TaskRepository(session)
        task_repo.update_progress(task_id, 20, stage="normalize_video")
        session.commit()

    config = NormalizationConfig()
    cmd = build_normalize_command(
        input_path=source_path,
        output_path=normalized_abs,
        probe=probe_before,
        config=config,
    )
    ffmpeg_version = get_ffmpeg_version()

    t0 = time.monotonic()
    try:
        run_ffmpeg(cmd, timeout=600, description="video normalization")
    except FFmpegError as e:
        _remove_if_exists(normalized_abs)
        with get_sync_session() as session:
            TaskRepository(session).set_error(task_id, "VIDEO_NORMALIZATION_FAILED", str(e))
            session.commit()
        clear_task_context()
        return _fail(task_id, video_id, "VIDEO_NORMALIZATION_FAILED", str(e))

    norm_runtime_ms = int((time.monotonic() - t0) * 1000)

    if not os.path.exists(normalized_abs):
        with get_sync_session() as session:
            TaskRepository(session).set_error(
                task_id,
                "VIDEO_NORMALIZATION_FAILED",
                "FFmpeg reported success but output file missing",
            )
            session.commit()
        clear_task_context()
        return _fail(
            task_id, video_id, "VIDEO_NORMALIZATION_FAILED", "Output file not found after ffmpeg"
        )

    # --- 6. FFprobe output → probe_after.json ---
    with get_sync_session() as session:
        task_repo = TaskRepository(session)
        task_repo.update_progress(task_id, 30, stage="normalize_video")
        session.commit()

    try:
        probe_after = probe_video(
            normalized_abs,
            output_dir=norm_dir_abs,
            label="probe_after",
        )
    except FFprobeError as e:
        with get_sync_session() as session:
            TaskRepository(session).set_error(task_id, "VIDEO_PROBE_FAILED", str(e))
            session.commit()
        clear_task_context()
        return _fail(task_id, video_id, "VIDEO_PROBE_FAILED", str(e))

    _write_json_atomic(probe_after_abs, probe_after.to_dict())

    # --- 7. Validate normalization ---
    validation_errors = validate_normalization(
        probe_before=probe_before,
        probe_after=probe_after,
        output_path=normalized_abs,
        config=config,
    )
    if validation_errors:
        with get_sync_session() as session:
            TaskRepository(session).set_error(
                task_id, "NORMALIZED_VIDEO_VALIDATION_FAILED", "; ".join(validation_errors)
            )
            session.commit()
        clear_task_context()
        return _fail(
            task_id, video_id, "NORMALIZED_VIDEO_VALIDATION_FAILED", "; ".join(validation_errors)
        )

    # --- 8. Compute SHA256 & write manifests ---
    with get_sync_session() as session:
        task_repo = TaskRepository(session)
        task_repo.update_progress(task_id, 35, stage="normalize_video")
        session.commit()

    import hashlib

    with open(normalized_abs, "rb") as f:
        norm_bytes = f.read()
    norm_sha256 = hashlib.sha256(norm_bytes).hexdigest()
    len(norm_bytes)

    probe_before.raw_json is not None and _sha256_file(source_path) or ""

    producer = ArtifactProducer(
        model_name="ffmpeg_normalizer",
        model_version=norm_version,
        code_revision="unknown",
        weight_revision="unknown",
    )

    # Write normalized.mp4 artifact
    writer.write_bytes_artifact(
        relative_path=normalized_rel,
        content=norm_bytes,
        artifact_type="normalized_video",
        artifact_id=f"{run_id}_norm",
        video_id=video_id,
        run_id=run_id,
        producer=producer,
        schema_version="1.0",
    )
    norm_uri = f"storage://{normalized_rel}"

    # Write probe_before artifact
    with open(probe_before_abs, "rb") as f:
        probe_before_bytes = f.read()
    writer.write_bytes_artifact(
        relative_path=probe_before_rel,
        content=probe_before_bytes,
        artifact_type="probe_before",
        artifact_id=f"{run_id}_probe_before",
        video_id=video_id,
        run_id=run_id,
        producer=producer,
        schema_version="1.0",
    )

    # Write probe_after artifact
    with open(probe_after_abs, "rb") as f:
        probe_after_bytes = f.read()
    writer.write_bytes_artifact(
        relative_path=probe_after_rel,
        content=probe_after_bytes,
        artifact_type="probe_after",
        artifact_id=f"{run_id}_probe_after",
        video_id=video_id,
        run_id=run_id,
        producer=producer,
        schema_version="1.0",
    )

    # --- 9. Save artifact DB records + update video + finalize ---
    with get_sync_session() as session:
        task_repo = TaskRepository(session)
        video_repo = VideoRepository(session)
        artifact_repo = ArtifactRepository(session)

        # Artifact records
        artifact_repo.create(
            artifact_id=f"{run_id}_norm",
            video_id=video_id,
            run_id=run_id,
            artifact_type="normalized_video",
            uri=norm_uri,
            format="mp4",
            schema_version="1.0",
            sha256=norm_sha256,
        )
        artifact_repo.create(
            artifact_id=f"{run_id}_probe_before",
            video_id=video_id,
            run_id=run_id,
            artifact_type="probe_before",
            uri=f"storage://{probe_before_rel}",
            format="json",
            schema_version="1.0",
        )
        artifact_repo.create(
            artifact_id=f"{run_id}_probe_after",
            video_id=video_id,
            run_id=run_id,
            artifact_type="probe_after",
            uri=f"storage://{probe_after_rel}",
            format="json",
            schema_version="1.0",
        )

        # Update video metadata
        video_repo.update_metadata(
            video_id,
            duration_ms=probe_after.duration_ms,
            fps_num=probe_after.fps_num,
            fps_den=probe_after.fps_den,
            width=probe_after.width,
            height=probe_after.height,
            audio_sample_rate=probe_after.audio_sample_rate,
            normalized_uri=norm_uri,
        )

        # Update ModelRun
        mr = session.get(ModelRun, run_id)
        if mr:
            mr.status = "SUCCEEDED"
            mr.runtime_ms = norm_runtime_ms
            mr.finished_at = datetime.now(timezone.utc)

        # Mark task as SUCCEEDED
        task_repo.update_status(task_id, "SUCCEEDED")
        task_repo.update_progress(task_id, 40, stage="normalize_video")
        session.commit()

    clear_task_context()

    return {
        "task_id": task_id,
        "video_id": video_id,
        "run_id": run_id,
        "normalized_artifact_id": f"{run_id}_norm",
        "normalized_artifact_uri": norm_uri,
        "status": "SUCCEEDED",
        "stage": "normalize_video",
        "metadata": {
            "duration_ms": probe_after.duration_ms,
            "fps_num": probe_after.fps_num,
            "fps_den": probe_after.fps_den,
            "width": probe_after.width,
            "height": probe_after.height,
            "audio_sample_rate": probe_after.audio_sample_rate,
            "video_codec": probe_after.video_codec,
            "pixel_format": probe_after.pixel_format,
            "validation_passed": True,
            "ffmpeg_version": ffmpeg_version,
            "runtime_ms": norm_runtime_ms,
        },
    }


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _resolve_uri(uri: str, storage_root: str) -> str:
    """Convert storage:// URI to local absolute path."""
    prefix = "storage://"
    if uri.startswith(prefix):
        return os.path.join(storage_root, uri[len(prefix) :])
    return uri


def _fail(task_id: str, video_id: str, code: str, message: str) -> dict:
    """Build a standardised failure result."""
    return {
        "task_id": task_id,
        "video_id": video_id,
        "status": "FAILED",
        "error": {"code": code, "message": message},
    }


def _write_json_atomic(path: str, data: dict) -> None:
    """Write JSON to a temp file then atomic rename."""
    import json

    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False, default=str)
    os.replace(tmp, path)


def _remove_if_exists(path: str) -> None:
    """Remove a file if it exists, silently."""
    try:
        os.remove(path)
    except OSError:
        pass


def _sha256_file(path: str) -> str:
    """Compute SHA-256 hex digest of a file."""
    import hashlib

    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(8192), b""):
            h.update(chunk)
    return h.hexdigest()
