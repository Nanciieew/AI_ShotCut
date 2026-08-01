"""
Celery tasks for shot boundary detection.

Delegates to OmniShotCut (or other shot detectors) via the
BaseModelAdapter interface. Each shot detector is selected by
the model_name parameter.
"""

import os
import time
import uuid
from datetime import datetime, timezone

from core.artifacts import ArtifactProducer
from core.artifacts.writer import ArtifactWriter
from core.database.models import ModelRun, Shot
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
# Adapter registry — maps model_name → Adapter class
# ---------------------------------------------------------------------------

_ADAPTER_REGISTRY: dict[str, type] = {}

try:
    from models.omnishotcut.adapter import OmniShotCutAdapter

    _ADAPTER_REGISTRY["omnishotcut"] = OmniShotCutAdapter
except ImportError:
    pass


def _get_adapter_class(model_name: str):
    """Look up an adapter class by model name."""
    cls = _ADAPTER_REGISTRY.get(model_name)
    if cls is None:
        raise ValueError(
            f"Unknown shot detection model: {model_name}. "
            f"Available: {list(_ADAPTER_REGISTRY.keys())}"
        )
    return cls


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


@app.task(name="shot.detect", bind=True, max_retries=2)
def detect_shots(
    self,
    task_id: str,
    video_id: str,
    model_name: str = "omnishotcut",
) -> dict:
    """Run shot boundary detection via registered model adapter.

    Reads the normalized video from artifact storage, invokes the
    model adapter, saves shots.json as an artifact, and writes shot
    records to the database.

    Parameters
    ----------
    task_id : str
        App-level task identifier.
    video_id : str
        Video to process (must have normalized_uri set).
    model_name : str
        Which shot detection model to use. Default: "omnishotcut".
    """
    set_task_context(task_id=task_id, video_id=video_id, model=model_name)

    storage_root = os.getenv("STORAGE_ROOT", "./data")
    writer = ArtifactWriter(storage_root)

    # --- 1. Validate model ---
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

        # --- 3. Update task → RUNNING ---
        task_repo.update_status(task_id, "RUNNING")
        task_repo.update_progress(task_id, 10, stage="detect_shots")

        # Create ModelRun
        run_id = uuid.uuid4().hex[:16]
        adapter = adapter_cls()
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
        with get_sync_session() as session:
            task_repo = TaskRepository(session)
            task_repo.update_progress(task_id, 30, stage="detect_shots")
            session.commit()

        t0 = time.monotonic()

        # Build unified input contract per IO_Rule §4.1
        model_input = {
            "schema_version": "1.0",
            "task_id": task_id,
            "video_id": video_id,
            "model": {"name": model_name, "version": adapter.version},
            "input": {
                "video_uri": f"storage://{normalized_uri[len('storage://') :]}"
                if normalized_uri.startswith("storage://")
                else normalized_uri
            },
            "parameters": {"mode": "clean_shot"},
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

    # --- 5. Extract shot data from adapter ---
    # adapter.predict() already completed: raw inference →
    # frame-diff filtering → ShotConverter → validation.
    # The structured shot list is available via adapter._last_shots.

    try:
        # Reconstruct shots from adapter internal state.
        # The adapter converts raw ranges internally; we tap into that
        # by calling predict with the same input and capturing the structured result.
        # Since adapter.predict() already validated the output,
        # we reconstruct shots from the metadata.

        # Alternative: parse the raw model output ourselves.
        # The cleanest approach is to have the adapter return shots inline.
        # For now we get it by running the converter directly.

        # Adapter.predict() already ran inference + filtering +
        # conversion + validation. Use stored _last_shots directly.
        shots_list: list[dict] = adapter._last_shots

        if not shots_list:
            with get_sync_session() as session:
                task_repo = TaskRepository(session)
                task_repo.set_error(task_id, "NO_SHOTS_DETECTED", "Model returned zero shots")
                mr = session.get(ModelRun, run_id)
                if mr:
                    mr.status = "FAILED"
                    mr.runtime_ms = runtime_ms
                    mr.finished_at = datetime.now(timezone.utc)
                session.commit()
            clear_task_context()
            raise NonRetryableTaskError("[NO_SHOTS_DETECTED] Model returned zero shots")

    except Exception as e:
        with get_sync_session() as session:
            task_repo = TaskRepository(session)
            task_repo.set_error(task_id, "SHOT_CONVERSION_FAILED", str(e))
            mr = session.get(ModelRun, run_id)
            if mr:
                mr.status = "FAILED"
                mr.finished_at = datetime.now(timezone.utc)
            session.commit()
        clear_task_context()
        raise NonRetryableTaskError(f"[SHOT_CONVERSION_FAILED] {e}")

    # --- 6. Save shots.json artifact ---
    with get_sync_session() as session:
        task_repo = TaskRepository(session)
        task_repo.update_progress(task_id, 70, stage="detect_shots")
        session.commit()

    project_id = video.project_id if video else "default"
    artifact_base = (
        f"projects/{project_id}/videos/{video_id}/artifacts/{model_name}/{adapter.version}"
    )
    shots_rel = f"{artifact_base}/shots.json"

    producer = ArtifactProducer(
        model_name=model_name,
        model_version=adapter.version,
        code_revision=getattr(adapter, "FIXED_COMMIT", "unknown"),
        weight_revision="unknown",
    )

    shots_data = {
        "video_id": video_id,
        "model": {"name": model_name, "version": adapter.version},
        "shots": shots_list,
    }

    manifest = writer.write_json_artifact(
        relative_path=shots_rel,
        data=shots_data,
        artifact_type="shots",
        artifact_id=f"{run_id}_shots",
        video_id=video_id,
        run_id=run_id,
        producer=producer,
        schema_version="1.0",
    )
    shots_uri = f"storage://{shots_rel}"
    shots_sha256 = manifest.output.sha256

    # --- 7. Write to DB ---
    with get_sync_session() as session:
        task_repo = TaskRepository(session)
        artifact_repo = ArtifactRepository(session)

        # Artifact record
        artifact_repo.create(
            artifact_id=f"{run_id}_shots",
            video_id=video_id,
            run_id=run_id,
            artifact_type="shots",
            uri=shots_uri,
            format="json",
            schema_version="1.0",
            sha256=shots_sha256,
        )

        # Bulk-insert shot records
        for s in shots_list:
            shot = Shot(
                shot_id=s["shot_id"],
                video_id=video_id,
                index=s["index"],
                start_ms=s["start_ms"],
                end_ms=s["end_ms"],
                start_frame=s.get("start_frame"),
                end_frame_exclusive=s.get("end_frame_exclusive"),
                boundary_type=s.get("boundary_type"),
                confidence=s.get("confidence"),
            )
            session.add(shot)

        # Update ModelRun
        mr = session.get(ModelRun, run_id)
        if mr:
            mr.status = "SUCCEEDED"
            mr.runtime_ms = runtime_ms
            mr.finished_at = datetime.now(timezone.utc)

        task_repo.update_progress(task_id, 70, stage="detect_shots")
        session.commit()

    clear_task_context()

    return {
        "task_id": task_id,
        "video_id": video_id,
        "run_id": run_id,
        "status": "SUCCEEDED",
        "stage": "detect_shots",
        "model": {"name": model_name, "version": adapter.version},
        "artifacts": {"shots": shots_uri},
        "metrics": {
            "shot_count": len(shots_list),
            "runtime_ms": runtime_ms,
        },
    }
