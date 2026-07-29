"""
Celery tasks for video preprocessing.

Handles:
  - Video normalization (FFmpeg re-encode + audio extraction)
  - Metadata extraction (ffprobe)
  - Artifact generation (normalized.mp4, audio.wav, metadata.json)
"""

import json
import os
import subprocess
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path

from workers.celery_app import app
from core.database.session_sync import get_sync_session
from core.database.repositories import (
    TaskRepository,
    VideoRepository,
    ArtifactRepository,
)
from core.database.models import ModelRun
from core.artifacts.writer import ArtifactWriter
from core.artifacts import ArtifactProducer
from core.logging.context import set_task_context, clear_task_context

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _run_ffprobe(video_path: str) -> dict:
    """Extract video metadata via ffprobe.

    Returns a dict with: duration_ms, fps_num, fps_den, width, height,
    audio_sample_rate, codec_name.
    """
    result = subprocess.run(
        [
            "ffprobe", "-v", "quiet",
            "-print_format", "json",
            "-show_format",
            "-show_streams",
            video_path,
        ],
        capture_output=True, text=True, timeout=30,
    )
    result.check_returncode()
    info = json.loads(result.stdout)

    meta: dict = {
        "duration_ms": 0,
        "fps_num": 24000,
        "fps_den": 1001,
        "width": 0,
        "height": 0,
        "audio_sample_rate": 0,
        "codec_name": "unknown",
    }

    # Duration from format
    fmt = info.get("format", {})
    if "duration" in fmt:
        meta["duration_ms"] = int(float(fmt["duration"]) * 1000)

    for stream in info.get("streams", []):
        codec_type = stream.get("codec_type", "")
        if codec_type == "video":
            meta["width"] = stream.get("width", 0)
            meta["height"] = stream.get("height", 0)
            meta["codec_name"] = stream.get("codec_name", "unknown")
            fps_str = stream.get("r_frame_rate", "24000/1001")
            num_str, den_str = fps_str.split("/")
            meta["fps_num"] = int(num_str)
            meta["fps_den"] = int(den_str)
        elif codec_type == "audio":
            meta["audio_sample_rate"] = int(stream.get("sample_rate", "0"))

    return meta


def _build_normalize_cmd(
    input_path: str,
    output_path: str,
    width: int,
    height: int,
) -> list[str]:
    """Build ffmpeg command for video normalization.

    Re-encodes to H.264 + AAC, standard resolution, consistent FPS.
    """
    return [
        "ffmpeg", "-y",
        "-i", input_path,
        "-c:v", "libx264",
        "-preset", "fast",
        "-crf", "23",
        "-pix_fmt", "yuv420p",
        "-vf", f"scale={width}:{height}:force_original_aspect_ratio=decrease,pad={width}:{height}:(ow-iw)/2:(oh-ih)/2",
        "-r", "24",
        "-c:a", "aac",
        "-b:a", "128k",
        "-ar", "16000",
        "-ac", "1",
        "-movflags", "+faststart",
        output_path,
    ]


def _build_audio_extract_cmd(
    input_path: str,
    output_path: str,
) -> list[str]:
    """Build ffmpeg command to extract 16kHz mono WAV audio."""
    return [
        "ffmpeg", "-y",
        "-i", input_path,
        "-vn",
        "-acodec", "pcm_s16le",
        "-ar", "16000",
        "-ac", "1",
        output_path,
    ]


# ---------------------------------------------------------------------------
# Task
# ---------------------------------------------------------------------------

@app.task(name="video.normalize", bind=True, max_retries=3)
def normalize_video(self, task_id: str, video_id: str) -> dict:
    """Normalize an uploaded video to a standard format.

    Steps:
      1. ffprobe → extract metadata
      2. ffmpeg → normalized.mp4 (H.264 24fps AAC)
      3. ffmpeg → audio.wav (16kHz mono)
      4. write metadata.json
      5. save artifacts + update DB
    """
    set_task_context(task_id=task_id, video_id=video_id, model="ffmpeg")

    storage_root = os.getenv("STORAGE_ROOT", "./data")
    writer = ArtifactWriter(storage_root)

    with get_sync_session() as session:
        task_repo = TaskRepository(session)
        video_repo = VideoRepository(session)
        artifact_repo = ArtifactRepository(session)

        # --- 1. Load video record ---
        video = video_repo.get(video_id)
        if video is None:
            clear_task_context()
            return {
                "task_id": task_id,
                "video_id": video_id,
                "status": "FAILED",
                "error": {"code": "VIDEO_NOT_FOUND", "message": f"Video {video_id} not in DB"},
            }

        # Resolve source path
        source_uri = video.source_uri
        if not source_uri:
            clear_task_context()
            return {
                "task_id": task_id,
                "video_id": video_id,
                "status": "FAILED",
                "error": {"code": "NO_SOURCE_URI", "message": "Video has no source_uri"},
            }

        source_path = _resolve_uri(source_uri, storage_root)
        if not os.path.exists(source_path):
            clear_task_context()
            return {
                "task_id": task_id,
                "video_id": video_id,
                "status": "FAILED",
                "error": {"code": "SOURCE_NOT_FOUND", "message": f"File not found: {source_path}"},
            }

        # --- 2. Update task → RUNNING ---
        task_repo.update_status(task_id, "RUNNING")
        task_repo.update_progress(task_id, 5, stage="normalize_video")

        # Create ModelRun record
        run_id = uuid.uuid4().hex[:16]
        model_run = ModelRun(
            run_id=run_id,
            task_id=task_id,
            video_id=video_id,
            model_name="ffmpeg",
            model_version="system",
            schema_version="1.0",
            status="RUNNING",
            device="cpu",
            started_at=datetime.now(timezone.utc),
        )
        session.add(model_run)
        session.commit()

    # --- 3. ffprobe metadata (no DB needed) ---
    try:
        meta = _run_ffprobe(source_path)
    except Exception as e:
        with get_sync_session() as session:
            task_repo = TaskRepository(session)
            task_repo.set_error(task_id, "FFPROBE_FAILED", str(e))
            session.commit()
        clear_task_context()
        return {
            "task_id": task_id,
            "video_id": video_id,
            "status": "FAILED",
            "error": {"code": "FFPROBE_FAILED", "message": str(e)},
        }

    # --- 4. Derive output paths ---
    project_id = video.project_id if video else "default"
    artifact_base = f"projects/{project_id}/videos/{video_id}/artifacts/ffmpeg/system"

    normalized_rel = f"{artifact_base}/normalized.mp4"
    audio_rel = f"{artifact_base}/audio.wav"
    metadata_rel = f"{artifact_base}/metadata.json"

    normalized_abs = os.path.join(storage_root, normalized_rel)
    audio_abs = os.path.join(storage_root, audio_rel)
    metadata_abs = os.path.join(storage_root, metadata_rel)

    os.makedirs(os.path.dirname(normalized_abs), exist_ok=True)

    # --- 5. ffmpeg normalize ---
    width = meta["width"] or 1920
    height = meta["height"] or 1080

    with get_sync_session() as session:
        task_repo = TaskRepository(session)
        task_repo.update_progress(task_id, 20, stage="normalize_video")
        session.commit()

    try:
        t0 = time.monotonic()
        subprocess.run(
            _build_normalize_cmd(source_path, normalized_abs, width, height),
            capture_output=True, text=True, timeout=600,
        ).check_returncode()
        norm_runtime_ms = int((time.monotonic() - t0) * 1000)
    except subprocess.CalledProcessError as e:
        with get_sync_session() as session:
            task_repo = TaskRepository(session)
            task_repo.set_error(task_id, "FFMPEG_NORMALIZE_FAILED", e.stderr[:500])
            session.commit()
        clear_task_context()
        return {
            "task_id": task_id,
            "video_id": video_id,
            "status": "FAILED",
            "error": {"code": "FFMPEG_NORMALIZE_FAILED", "message": e.stderr[:500]},
        }

    # --- 6. ffmpeg extract audio ---
    with get_sync_session() as session:
        task_repo = TaskRepository(session)
        task_repo.update_progress(task_id, 50, stage="normalize_video")
        session.commit()

    try:
        t0 = time.monotonic()
        subprocess.run(
            _build_audio_extract_cmd(source_path, audio_abs),
            capture_output=True, text=True, timeout=300,
        ).check_returncode()
        audio_runtime_ms = int((time.monotonic() - t0) * 1000)
    except subprocess.CalledProcessError as e:
        with get_sync_session() as session:
            task_repo = TaskRepository(session)
            task_repo.set_error(task_id, "FFMPEG_AUDIO_FAILED", e.stderr[:500])
            session.commit()
        clear_task_context()
        return {
            "task_id": task_id,
            "video_id": video_id,
            "status": "FAILED",
            "error": {"code": "FFMPEG_AUDIO_FAILED", "message": e.stderr[:500]},
        }

    # --- 7. Write metadata.json ---
    metadata_content = {
        "video_id": video_id,
        "duration_ms": meta["duration_ms"],
        "fps_num": meta["fps_num"],
        "fps_den": meta["fps_den"],
        "width": meta["width"],
        "height": meta["height"],
        "audio_sample_rate": meta["audio_sample_rate"],
        "codec_name": meta["codec_name"],
    }
    os.makedirs(os.path.dirname(metadata_abs), exist_ok=True)
    with open(metadata_abs, "w", encoding="utf-8") as f:
        json.dump(metadata_content, f, indent=2)

    # --- 8. Write artifacts + manifests ---
    with get_sync_session() as session:
        task_repo = TaskRepository(session)
        task_repo.update_progress(task_id, 75, stage="normalize_video")
        session.commit()

    producer = ArtifactProducer(
        model_name="ffmpeg",
        model_version="system",
        code_revision=None,
        weight_revision=None,
    )

    # normalized.mp4
    with open(normalized_abs, "rb") as f:
        norm_bytes = f.read()
    norm_manifest = writer.write_bytes_artifact(
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
    norm_sha256 = norm_manifest.output.sha256

    # audio.wav
    with open(audio_abs, "rb") as f:
        audio_bytes = f.read()
    writer.write_bytes_artifact(
        relative_path=audio_rel,
        content=audio_bytes,
        artifact_type="audio_wav",
        artifact_id=f"{run_id}_audio",
        video_id=video_id,
        run_id=run_id,
        producer=producer,
        schema_version="1.0",
    )
    audio_uri = f"storage://{audio_rel}"

    # metadata.json
    writer.write_json_artifact(
        relative_path=metadata_rel,
        data=metadata_content,
        artifact_type="video_metadata",
        artifact_id=f"{run_id}_meta",
        video_id=video_id,
        run_id=run_id,
        producer=producer,
        schema_version="1.0",
    )
    metadata_uri = f"storage://{metadata_rel}"

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
            artifact_id=f"{run_id}_audio",
            video_id=video_id,
            run_id=run_id,
            artifact_type="audio_wav",
            uri=audio_uri,
            format="wav",
            schema_version="1.0",
        )
        artifact_repo.create(
            artifact_id=f"{run_id}_meta",
            video_id=video_id,
            run_id=run_id,
            artifact_type="video_metadata",
            uri=metadata_uri,
            format="json",
            schema_version="1.0",
        )

        # Update video metadata
        video_repo.update_metadata(
            video_id,
            duration_ms=meta["duration_ms"],
            fps_num=meta["fps_num"],
            fps_den=meta["fps_den"],
            width=meta["width"],
            height=meta["height"],
            audio_sample_rate=meta["audio_sample_rate"],
            normalized_uri=norm_uri,
            audio_uri=audio_uri,
        )

        # Update ModelRun
        mr = session.get(ModelRun, run_id)
        if mr:
            mr.status = "SUCCEEDED"
            mr.runtime_ms = norm_runtime_ms + audio_runtime_ms
            mr.finished_at = datetime.now(timezone.utc)

        # Mark task as SUCCEEDED
        task_repo.update_status(task_id, "SUCCEEDED")
        task_repo.update_progress(task_id, 100, stage="normalize_video")
        session.commit()

    clear_task_context()

    return {
        "task_id": task_id,
        "video_id": video_id,
        "run_id": run_id,
        "status": "SUCCEEDED",
        "stage": "normalize_video",
        "artifacts": {
            "normalized_video": norm_uri,
            "audio_wav": audio_uri,
            "metadata": metadata_uri,
        },
        "metadata": metadata_content,
        "runtime_ms": norm_runtime_ms + audio_runtime_ms,
    }


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _resolve_uri(uri: str, storage_root: str) -> str:
    """Convert storage:// URI to local absolute path."""
    prefix = "storage://"
    if uri.startswith(prefix):
        return os.path.join(storage_root, uri[len(prefix):])
    return uri
