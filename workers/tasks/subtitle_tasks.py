"""
Celery tasks for subtitle generation.

Delegates to Doubao ASR adapter for speech-to-text.
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
from core.media.exceptions import NonRetryableTaskError
from workers.celery_app import app


@app.task(name="subtitle.transcribe", bind=True, max_retries=1)
def transcribe(self, task_id: str, video_id: str) -> dict:
    """Generate subtitles via Doubao ASR adapter.

    Reads normalized video, extracts audio, runs ASR, saves subtitles.json.

    Parameters
    ----------
    task_id : str  App-level task identifier.
    video_id : str  Video to process (must have normalized_uri).
    """
    model_name = "whisper"
    set_task_context(task_id=task_id, video_id=video_id, model=model_name)

    storage_root = os.getenv("STORAGE_ROOT", "./data")
    writer = ArtifactWriter(storage_root)

    # Load adapter
    try:
        from models.whisper.adapter import WhisperAdapter

        adapter_cls = WhisperAdapter
    except ImportError as e:
        clear_task_context()
        raise NonRetryableTaskError(f"[IMPORT_FAILED] {e}")

    # Load video
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
            raise NonRetryableTaskError("[NOT_NORMALIZED] Video has no normalized_uri.")
        video_path = os.path.join(
            storage_root,
            normalized_uri[len("storage://") :]
            if normalized_uri.startswith("storage://")
            else normalized_uri,
        )
        if not os.path.exists(video_path):
            clear_task_context()
            raise NonRetryableTaskError(f"[FILE_NOT_FOUND] {video_path}")

        task_repo.update_status(task_id, "RUNNING")
        task_repo.update_progress(task_id, 10, stage="transcribe")

        adapter = adapter_cls()
        run_id = uuid.uuid4().hex[:16]
        model_run = ModelRun(
            run_id=run_id,
            task_id=task_id,
            video_id=video_id,
            model_name=model_name,
            model_version="1.0.0",
            schema_version="1.0",
            status="RUNNING",
            device="cpu",
            started_at=datetime.now(timezone.utc),
        )
        session.add(model_run)
        session.commit()

    # Load + transcribe
    try:
        adapter.load()
    except Exception as e:
        with get_sync_session() as session:
            TaskRepository(session).set_error(task_id, "MODEL_LOAD_FAILED", str(e))
            mr = session.get(ModelRun, run_id)
            if mr:
                mr.status = "FAILED"
                mr.finished_at = datetime.now(timezone.utc)
            session.commit()
        clear_task_context()
        raise NonRetryableTaskError(f"[MODEL_LOAD_FAILED] {e}")

    try:
        t0 = time.monotonic()
        output = adapter.predict(
            {
                "task_id": task_id,
                "video_id": video_id,
                "model": {"name": model_name, "version": "1.0.0"},
                "input": {"video_uri": normalized_uri},
                "parameters": {},
            }
        )
        runtime_ms = int((time.monotonic() - t0) * 1000)
    except Exception as e:
        with get_sync_session() as session:
            TaskRepository(session).set_error(task_id, "TRANSCRIPTION_FAILED", str(e))
            mr = session.get(ModelRun, run_id)
            if mr:
                mr.status = "FAILED"
                mr.finished_at = datetime.now(timezone.utc)
            session.commit()
        clear_task_context()
        raise NonRetryableTaskError(f"[TRANSCRIPTION_FAILED] {e}")

    if output.get("status") != "SUCCEEDED":
        err = output.get("error", {})
        with get_sync_session() as session:
            TaskRepository(session).set_error(
                task_id, err.get("code", "FAILED"), err.get("message", "")
            )
            mr = session.get(ModelRun, run_id)
            if mr:
                mr.status = "FAILED"
                mr.runtime_ms = runtime_ms
                mr.finished_at = datetime.now(timezone.utc)
            session.commit()
        clear_task_context()
        raise NonRetryableTaskError(f"[{err.get('code', 'FAILED')}] {err.get('message', '')}")

    # Save artifact
    segments = output.get("artifacts", {}).get("subtitle_segments", [])
    project_id = video.project_id if video else "default"
    artifact_base = f"projects/{project_id}/videos/{video_id}/artifacts/{model_name}/1.0.0"
    subtitles_rel = f"{artifact_base}/subtitles.json"

    producer = ArtifactProducer(model_name=model_name, model_version="1.0.0")
    subtitles_data = {
        "video_id": video_id,
        "model": {"name": model_name, "version": "1.0.0"},
        "subtitle_source": "doubao_asr",
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
    )

    with get_sync_session() as session:
        ArtifactRepository(session).create(
            artifact_id=f"{run_id}_subtitles",
            video_id=video_id,
            run_id=run_id,
            artifact_type="subtitle_segments",
            uri=f"storage://{subtitles_rel}",
            format="json",
            sha256=manifest.output.sha256,
        )
        mr = session.get(ModelRun, run_id)
        if mr:
            mr.status = "SUCCEEDED"
            mr.runtime_ms = runtime_ms
            mr.finished_at = datetime.now(timezone.utc)
        TaskRepository(session).update_progress(task_id, 50, stage="transcribe")
        session.commit()

    clear_task_context()
    return {
        "task_id": task_id,
        "video_id": video_id,
        "run_id": run_id,
        "status": "SUCCEEDED",
        "stage": "transcribe",
        "artifacts": {"subtitles": f"storage://{subtitles_rel}"},
        "metrics": {"segment_count": len(segments), "runtime_ms": runtime_ms},
    }
