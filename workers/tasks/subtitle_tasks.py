"""
Celery tasks for subtitle generation / parsing.

Delegates to Whisper adapter for speech-to-text transcription.
"""

import json
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
from core.media.exceptions import NonRetryableTaskError
from workers.celery_app import app

# ---------------------------------------------------------------------------
# Adapter registry
# ---------------------------------------------------------------------------

_ADAPTER_REGISTRY: dict[str, type] = {}

try:
    from models.whisper.adapter import WhisperAdapter

    _ADAPTER_REGISTRY["whisper"] = WhisperAdapter
except ImportError:
    pass


def _get_adapter_class(model_name: str):
    cls = _ADAPTER_REGISTRY.get(model_name)
    if cls is None:
        raise ValueError(
            f"Unknown subtitle model: {model_name}. "
            f"Available: {list(_ADAPTER_REGISTRY.keys())}"
        )
    return cls


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _resolve_uri(uri: str, storage_root: str) -> str:
    prefix = "storage://"
    if uri.startswith(prefix):
        return os.path.join(storage_root, uri[len(prefix) :])
    return uri


# ---------------------------------------------------------------------------
# Task
# ---------------------------------------------------------------------------


@app.task(name="subtitle.transcribe", bind=True, max_retries=1)
def transcribe(self, task_id: str, video_id: str) -> dict:
    """Generate subtitles via Whisper transcription.

    Reads the normalized video from artifact storage, extracts audio,
    runs Whisper, saves subtitles.json as an artifact.

    Parameters
    ----------
    task_id : str
        App-level task identifier.
    video_id : str
        Video to process (must have normalized_uri set).
    """
    model_name = "whisper"
    set_task_context(task_id=task_id, video_id=video_id, model=model_name)

    storage_root = os.getenv("STORAGE_ROOT", "./data")
    writer = ArtifactWriter(storage_root)

    # --- 1. Validate adapter ---
    try:
        adapter_cls = _get_adapter_class(model_name)
    except ValueError as e:
        clear_task_context()
        raise NonRetryableTaskError(f"[UNKNOWN_MODEL] {e}")

    # --- 2. Load video record ---
    with get_sync_session() as session:
        task_repo = TaskRepository(session)
        video_repo = VideoRepository(session)

        video = video_repo.get(video_id)
        if video is None:
            clear_task_context()
            raise NonRetryableTaskError(
                f"[VIDEO_NOT_FOUND] Video {video_id} not in DB"
            )

        normalized_uri = video.normalized_uri
        if not normalized_uri:
            clear_task_context()
            raise NonRetryableTaskError(
                "[NOT_NORMALIZED] Video has no normalized_uri."
            )

        video_path = _resolve_uri(normalized_uri, storage_root)
        if not os.path.exists(video_path):
            clear_task_context()
            raise NonRetryableTaskError(
                f"[FILE_NOT_FOUND] Normalized video missing: {video_path}"
            )

        # --- 3. Update task → RUNNING ---
        task_repo.update_status(task_id, "RUNNING")
        task_repo.update_progress(task_id, 10, stage="transcribe")

        adapter = adapter_cls()
        run_id = uuid.uuid4().hex[:16]
        model_run = ModelRun(
            run_id=run_id,
            task_id=task_id,
            video_id=video_id,
            model_name=model_name,
            model_version=adapter.version,
            schema_version="1.0",
            status="RUNNING",
            device="cpu",
            started_at=datetime.now(timezone.utc),
        )
        session.add(model_run)
        session.commit()

    # --- 4. Load model + run inference ---
    try:
        adapter.load()
    except Exception as e:
        with get_sync_session() as session:
            task_repo = TaskRepository(session)
            task_repo.set_error(task_id, "MODEL_LOAD_FAILED", str(e))
            mr = session.get(ModelRun, run_id)
            if mr:
                mr.status = "FAILED"
                mr.finished_at = datetime.now(timezone.utc)
            session.commit()
        clear_task_context()
        raise NonRetryableTaskError(f"[MODEL_LOAD_FAILED] {e}")

    try:
        t0 = time.monotonic()
        model_input = {
            "schema_version": "1.0",
            "task_id": task_id,
            "video_id": video_id,
            "model": {"name": model_name, "version": adapter.version},
            "input": {"video_uri": normalized_uri},
            "parameters": {"word_timestamps": True},
        }

        output = adapter.predict(model_input)
        runtime_ms = int((time.monotonic() - t0) * 1000)

        if output.get("status") == "FAILED":
            error_info = output.get("error", {})
            with get_sync_session() as session:
                task_repo = TaskRepository(session)
                task_repo.set_error(
                    task_id,
                    error_info.get("code", "INFERENCE_FAILED"),
                    error_info.get("message", "Unknown inference error"),
                )
                mr = session.get(ModelRun, run_id)
                if mr:
                    mr.status = "FAILED"
                    mr.runtime_ms = runtime_ms
                    mr.finished_at = datetime.now(timezone.utc)
                session.commit()
            clear_task_context()
            raise NonRetryableTaskError(
                f"[{error_info.get('code', 'INFERENCE_FAILED')}] "
                + error_info.get("message", "Unknown inference error")
            )

    except Exception as e:
        with get_sync_session() as session:
            task_repo = TaskRepository(session)
            task_repo.set_error(task_id, "MODEL_INFERENCE_FAILED", str(e))
            mr = session.get(ModelRun, run_id)
            if mr:
                mr.status = "FAILED"
                mr.finished_at = datetime.now(timezone.utc)
            session.commit()
        clear_task_context()
        raise NonRetryableTaskError(f"[MODEL_INFERENCE_FAILED] {e}")

    # --- 5. Save subtitles.json artifact ---
    segments = output.get("artifacts", {}).get("subtitle_segments", [])
    if not segments:
        with get_sync_session() as session:
            task_repo = TaskRepository(session)
            task_repo.set_error(task_id, "NO_SEGMENTS", "Whisper returned zero segments")
            mr = session.get(ModelRun, run_id)
            if mr:
                mr.status = "FAILED"
                mr.runtime_ms = runtime_ms
                mr.finished_at = datetime.now(timezone.utc)
            session.commit()
        clear_task_context()
        raise NonRetryableTaskError("[NO_SEGMENTS] Whisper returned zero segments")

    project_id = video.project_id if video else "default"
    artifact_base = (
        f"projects/{project_id}/videos/{video_id}/"
        f"artifacts/{model_name}/{adapter.version}"
    )
    subtitles_rel = f"{artifact_base}/subtitles.json"

    producer = ArtifactProducer(
        model_name=model_name,
        model_version=adapter.version,
        code_revision=getattr(adapter, "FIXED_COMMIT", "unknown"),
        weight_revision="unknown",
    )

    subtitles_data = {
        "video_id": video_id,
        "model": {"name": model_name, "version": adapter.version},
        "subtitle_source": "whisper",
        "language": output.get("metrics", {}).get("language", "unknown"),
        "subtitle_segments": segments,
    }

    manifest = writer.write_json_artifact(
        relative_path=subtitles_rel,
        data=subtitles_data,
        artifact_type="subtitle_segments",
        artifact_id=f"{run_id}_subtitles",
        video_id=video_id,
        run_id=run_id,
        producer=producer,
        schema_version="1.0",
    )
    subtitles_uri = f"storage://{subtitles_rel}"
    subtitles_sha256 = manifest.output.sha256

    # --- 6. Write to DB ---
    with get_sync_session() as session:
        task_repo = TaskRepository(session)
        artifact_repo = ArtifactRepository(session)

        artifact_repo.create(
            artifact_id=f"{run_id}_subtitles",
            video_id=video_id,
            run_id=run_id,
            artifact_type="subtitle_segments",
            uri=subtitles_uri,
            format="json",
            schema_version="1.0",
            sha256=subtitles_sha256,
        )

        mr = session.get(ModelRun, run_id)
        if mr:
            mr.status = "SUCCEEDED"
            mr.runtime_ms = runtime_ms
            mr.finished_at = datetime.now(timezone.utc)

        task_repo.update_progress(task_id, 50, stage="transcribe")
        session.commit()

    clear_task_context()

    return {
        "task_id": task_id,
        "video_id": video_id,
        "run_id": run_id,
        "status": "SUCCEEDED",
        "stage": "transcribe",
        "model": {"name": model_name, "version": adapter.version},
        "artifacts": {"subtitles": subtitles_uri},
        "metrics": {
            "segment_count": len(segments),
            "runtime_ms": runtime_ms,
        },
    }
