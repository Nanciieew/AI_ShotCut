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
from core.media.exceptions import (
    FFmpegError,
    FFprobeError,
    NonRetryableTaskError,
)
from core.media.ffmpeg import (
    build_keyframe_extract_per_shot_commands,
    build_normalize_command,
    get_ffmpeg_version,
    run_ffmpeg,
    validate_keyframe_output,
)
from core.media.ffprobe import probe_video, run_ffprobe
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
            raise NonRetryableTaskError(f"[VIDEO_NOT_FOUND] Video {video_id} not in DB")

        source_uri = video.source_uri
        if not source_uri:
            clear_task_context()
            raise NonRetryableTaskError("[NO_SOURCE_URI] Video has no source_uri")

        source_path = _resolve_uri(source_uri, storage_root)
        if not os.path.exists(source_path):
            clear_task_context()
            raise NonRetryableTaskError(f"[SOURCE_NOT_FOUND] File not found: {source_path}")

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
        raise NonRetryableTaskError(f"[VIDEO_PROBE_FAILED] {e}")

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
        run_ffmpeg(cmd, timeout=3600, description="video normalization")
    except FFmpegError as e:
        _remove_if_exists(normalized_abs)
        with get_sync_session() as session:
            TaskRepository(session).set_error(task_id, "VIDEO_NORMALIZATION_FAILED", str(e))
            session.commit()
        clear_task_context()
        raise NonRetryableTaskError(f"[VIDEO_NORMALIZATION_FAILED] {e}")

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
        raise NonRetryableTaskError(
            "[VIDEO_NORMALIZATION_FAILED] Output file not found after ffmpeg"
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
        raise NonRetryableTaskError(f"[VIDEO_PROBE_FAILED] {e}")

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
        raise NonRetryableTaskError(
            "[NORMALIZED_VIDEO_VALIDATION_FAILED] " + "; ".join(validation_errors)
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

        # Update ModelRun — DO NOT mark task SUCCEEDED (only final.pipeline_complete does)
        mr = session.get(ModelRun, run_id)
        if mr:
            mr.status = "SUCCEEDED"
            mr.runtime_ms = norm_runtime_ms
            mr.finished_at = datetime.now(timezone.utc)

        task_repo.update_progress(task_id, 30, stage="normalize_video")
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


# ---------------------------------------------------------------------------
# Proxy Task
# ---------------------------------------------------------------------------


@app.task(name="video.build_shot_proxy", bind=True, max_retries=1)
def build_shot_proxy(self, task_id: str, video_id: str) -> dict:
    """Build 320×180 proxy video for OmniShotCut shot detection.

    Reads normalized_video artifact, generates proxy, saves as artifact.
    Proxy: H.264, yuv420p, 320×180, no audio, same FPS/frames.

    Per spec: OmniShotCut_320x180_Proxy视频方案.md §5.3
    """
    from core.media.ffmpeg import build_shot_proxy_command, run_ffmpeg, validate_proxy_output

    set_task_context(task_id=task_id, video_id=video_id, model="shot_proxy")

    storage_root = os.getenv("STORAGE_ROOT", "./data")
    writer = ArtifactWriter(storage_root)

    with get_sync_session() as session:
        video_repo = VideoRepository(session)
        task_repo = TaskRepository(session)

        video = video_repo.get(video_id)
        if video is None:
            clear_task_context()
            return _fail(task_id, video_id, "VIDEO_NOT_FOUND", f"Video {video_id} not in DB")

        normalized_uri = video.normalized_uri
        if not normalized_uri:
            clear_task_context()
            return _fail(task_id, video_id, "NOT_NORMALIZED", "Run normalize_video first")

        normalized_path = _resolve_uri(normalized_uri, storage_root)
        if not os.path.exists(normalized_path):
            clear_task_context()
            return _fail(
                task_id,
                video_id,
                "NORMALIZED_NOT_FOUND",
                f"Normalized video missing: {normalized_path}",
            )

        # Probe normalized for validation reference
        probe_norm = run_ffprobe(normalized_path)

        task_repo.update_status(task_id, "RUNNING")
        task_repo.update_progress(task_id, 45, stage="build_shot_proxy")

        run_id = uuid.uuid4().hex[:16]
        model_run = ModelRun(
            run_id=run_id,
            task_id=task_id,
            video_id=video_id,
            model_name="shot_proxy",
            model_version="1.0.0",
            schema_version="1.0",
            status="RUNNING",
            device="cpu",
            started_at=datetime.now(timezone.utc),
        )
        session.add(model_run)
        session.commit()

    # Build proxy paths
    project_id = video.project_id if video else "default"
    proxy_base = f"projects/{project_id}/videos/{video_id}/artifacts/shot_proxy/1.0.0"
    proxy_dir = os.path.join(storage_root, proxy_base)
    os.makedirs(proxy_dir, exist_ok=True)

    proxy_rel = f"{proxy_base}/shot_proxy_320x180.mp4"
    proxy_abs = os.path.join(storage_root, proxy_rel)

    # Build + run proxy command
    cmd = build_shot_proxy_command(
        input_path=normalized_path,
        output_path=proxy_abs,
        probe=probe_norm,
    )
    t0 = time.monotonic()
    try:
        run_ffmpeg(cmd, timeout=3600, description="shot proxy generation")
    except FFmpegError as e:
        _remove_if_exists(proxy_abs)
        with get_sync_session() as s:
            TaskRepository(s).set_error(task_id, "SHOT_PROXY_FAILED", str(e))
            s.commit()
        clear_task_context()
        return _fail(task_id, video_id, "SHOT_PROXY_FAILED", str(e))

    runtime_ms = int((time.monotonic() - t0) * 1000)

    # Validate
    errors = validate_proxy_output(proxy_abs, probe_normalized=probe_norm)
    if errors:
        with get_sync_session() as s:
            TaskRepository(s).set_error(task_id, "SHOT_PROXY_VALIDATION_FAILED", "; ".join(errors))
            s.commit()
        clear_task_context()
        return _fail(task_id, video_id, "SHOT_PROXY_VALIDATION_FAILED", "; ".join(errors))

    # Save artifact + manifest
    proxy_sha = _sha256_file(proxy_abs)
    producer = ArtifactProducer(
        model_name="shot_proxy",
        model_version="1.0.0",
        code_revision="unknown",
        weight_revision="unknown",
    )
    writer.write_json_artifact(
        relative_path=proxy_rel,
        data={
            "schema_version": "1.0",
            "artifact_type": "shot_proxy_video",
            "width": 320,
            "height": 180,
            "fps_num": probe_norm.fps_num,
            "fps_den": probe_norm.fps_den,
            "frame_count": probe_norm.frame_count,
            "duration_ms": probe_norm.duration_ms,
            "video_codec": "h264",
            "pixel_format": "yuv420p",
            "has_audio": False,
            "scale_policy": "fit_pad",
        },
        artifact_type="shot_proxy_video",
        artifact_id=f"{run_id}_proxy",
        video_id=video_id,
        run_id=run_id,
        producer=producer,
        schema_version="1.0",
    )
    proxy_uri = f"storage://{proxy_rel}"

    with get_sync_session() as s:
        ArtifactRepository(s).create(
            artifact_id=f"{run_id}_proxy",
            video_id=video_id,
            run_id=run_id,
            artifact_type="shot_proxy_video",
            uri=proxy_uri,
            format="mp4",
            schema_version="1.0",
            sha256=proxy_sha,
        )
        mr = s.get(ModelRun, run_id)
        if mr:
            mr.status = "SUCCEEDED"
            mr.runtime_ms = runtime_ms
            mr.finished_at = datetime.now(timezone.utc)
        TaskRepository(s).update_progress(task_id, 50, stage="build_shot_proxy")
        s.commit()

    clear_task_context()
    return {
        "task_id": task_id,
        "video_id": video_id,
        "run_id": run_id,
        "status": "SUCCEEDED",
        "stage": "build_shot_proxy",
        "proxy_artifact_id": f"{run_id}_proxy",
        "proxy_artifact_uri": proxy_uri,
        "runtime_ms": runtime_ms,
    }


# ---------------------------------------------------------------------------
# Keyframe extraction Task
# ---------------------------------------------------------------------------


@app.task(name="video.extract_keyframes", bind=True, max_retries=1)
def extract_keyframes(self, task_id: str, video_id: str, shots_artifact_uri: str = "") -> dict:
    """Extract keyframes (start/mid/end) per shot from normalized.mp4.

    Reads normalized_video artifact + shots artifact, extracts 3 keyframes
    per shot using FFmpeg select filter. Saves as shot_keyframes artifact.

    Same strategy as SceneSeg keyf_img_saver: start frame, mid frame, end-1 frame.
    Extracted from normalized.mp4 (NOT proxy — per Proxy doc §1).
    """
    set_task_context(task_id=task_id, video_id=video_id, model="keyframe_extractor")

    storage_root = os.getenv("STORAGE_ROOT", "./data")
    writer = ArtifactWriter(storage_root)

    with get_sync_session() as session:
        video_repo = VideoRepository(session)
        task_repo = TaskRepository(session)

        video = video_repo.get(video_id)
        if video is None:
            clear_task_context()
            return _fail(task_id, video_id, "VIDEO_NOT_FOUND", f"Video {video_id} not in DB")

        normalized_uri = video.normalized_uri
        if not normalized_uri:
            clear_task_context()
            return _fail(task_id, video_id, "NOT_NORMALIZED", "Run normalize_video first")

        normalized_path = _resolve_uri(normalized_uri, storage_root)
        if not os.path.exists(normalized_path):
            clear_task_context()
            return _fail(
                task_id,
                video_id,
                "NORMALIZED_NOT_FOUND",
                f"Normalized video missing: {normalized_path}",
            )

        # Load shots
        if not shots_artifact_uri:
            # Find latest shots artifact from DB
            artifacts = ArtifactRepository(session).list_by_video(video_id)
            shot_artifacts = [
                a for a in artifacts if a.artifact_type in ("shots", "shot_boundaries")
            ]
            if not shot_artifacts:
                clear_task_context()
                return _fail(
                    task_id,
                    video_id,
                    "NO_SHOTS",
                    "No shots artifact found. Run detect_shots first.",
                )
            shots_uri = shot_artifacts[-1].uri
        else:
            shots_uri = shots_artifact_uri

        shots_path = _resolve_uri(shots_uri, storage_root)
        if not os.path.exists(shots_path):
            clear_task_context()
            return _fail(task_id, video_id, "SHOTS_NOT_FOUND", f"Shots file missing: {shots_path}")

        import json as _json

        with open(shots_path) as f:
            shots_data = _json.load(f)
        shots = shots_data.get("shots", [])
        if not shots:
            clear_task_context()
            return _fail(task_id, video_id, "NO_SHOTS", "Shots list is empty")

        task_repo.update_status(task_id, "RUNNING")
        task_repo.update_progress(task_id, 55, stage="extract_keyframes")

        run_id = uuid.uuid4().hex[:16]
        model_run = ModelRun(
            run_id=run_id,
            task_id=task_id,
            video_id=video_id,
            model_name="keyframe_extractor",
            model_version="1.0.0",
            schema_version="1.0",
            status="RUNNING",
            device="cpu",
            started_at=datetime.now(timezone.utc),
        )
        session.add(model_run)
        session.commit()

    # Build output paths
    project_id = video.project_id if video else "default"
    kf_base = f"projects/{project_id}/videos/{video_id}/artifacts/shot_keyframes/1.0.0"
    kf_dir = os.path.join(storage_root, kf_base)
    os.makedirs(kf_dir, exist_ok=True)

    # Extract keyframes
    positions = ["start", "mid", "end"]
    commands = build_keyframe_extract_per_shot_commands(
        video_path=normalized_path,
        output_dir=kf_dir,
        shots=shots,
        positions=positions,
    )

    t0 = time.monotonic()
    failed_shots = []
    for shot_id, cmd in commands:
        try:
            run_ffmpeg(cmd, timeout=60, description=f"keyframe {shot_id}")
        except FFmpegError as e:
            failed_shots.append(f"{shot_id}: {e}")

    runtime_ms = int((time.monotonic() - t0) * 1000)

    # Validate
    errors = validate_keyframe_output(kf_dir, shots, positions)
    if errors:
        with get_sync_session() as s:
            TaskRepository(s).set_error(
                task_id,
                "KEYFRAME_VALIDATION_FAILED",
                f"Missing {len(errors)} keyframes: {errors[:5]}",
            )
            s.commit()
        clear_task_context()
        return _fail(
            task_id, video_id, "KEYFRAME_VALIDATION_FAILED", f"{len(errors)} missing: {errors[:3]}"
        )

    # Save artifact
    total_keyframes = len(shots) * len(positions)
    producer = ArtifactProducer(
        model_name="keyframe_extractor",
        model_version="1.0.0",
        code_revision="unknown",
        weight_revision="unknown",
    )

    keyframe_meta = {
        "schema_version": "1.0",
        "artifact_type": "shot_keyframes",
        "total_shots": len(shots),
        "keyframes_per_shot": len(positions),
        "total_keyframes": total_keyframes,
        "positions": positions,
        "source": "normalized.mp4",
        "strategy": "SceneSeg_keyf_img_saver",
    }
    writer.write_json_artifact(
        relative_path=f"{kf_base}/shot_keyframes.json",
        data=keyframe_meta,
        artifact_type="shot_keyframes",
        artifact_id=f"{run_id}_kf",
        video_id=video_id,
        run_id=run_id,
        producer=producer,
        schema_version="1.0",
    )
    kf_uri = f"storage://{kf_base}"

    with get_sync_session() as s:
        ArtifactRepository(s).create(
            artifact_id=f"{run_id}_kf",
            video_id=video_id,
            run_id=run_id,
            artifact_type="shot_keyframes",
            uri=kf_uri,
            format="dir",
            schema_version="1.0",
        )
        mr = s.get(ModelRun, run_id)
        if mr:
            mr.status = "SUCCEEDED"
            mr.runtime_ms = runtime_ms
            mr.finished_at = datetime.now(timezone.utc)
        TaskRepository(s).update_progress(task_id, 60, stage="extract_keyframes")
        s.commit()

    clear_task_context()
    return {
        "task_id": task_id,
        "video_id": video_id,
        "run_id": run_id,
        "status": "SUCCEEDED",
        "stage": "extract_keyframes",
        "keyframes_artifact_id": f"{run_id}_kf",
        "keyframes_artifact_uri": kf_uri,
        "total_keyframes": total_keyframes,
        "failed_shots": failed_shots,
        "runtime_ms": runtime_ms,
    }


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


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
