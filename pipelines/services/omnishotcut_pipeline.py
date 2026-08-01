"""OmniShotCut pipeline service — local executor.

Orchestrates the complete single-model pipeline without requiring
Celery, Redis, PostgreSQL, or Docker. Uses the same:
  - core.media (ffprobe, ffmpeg, normalization)
  - OmniShotCut adapter / converter / validation
  - Artifact writer + manifest
  - Schema definitions

This is the SAME service that future Celery tasks will call.
Per §19: do NOT create separate LocalPipeline and DockerPipeline.
"""

import hashlib
import json
import time
import uuid
from dataclasses import dataclass, field
from pathlib import Path

from core.artifacts import ArtifactProducer
from core.artifacts.writer import ArtifactWriter
from core.media.exceptions import (
    FFmpegError,
    FFprobeError,
)
from core.media.ffmpeg import build_normalize_command, get_ffmpeg_version, run_ffmpeg
from core.media.ffprobe import run_ffprobe
from core.media.normalization import validate_normalization
from core.media.schemas import FFprobeResult, NormalizationConfig

# ---------------------------------------------------------------------------
# Result types
# ---------------------------------------------------------------------------


@dataclass
class PipelineResult:
    """Standard result from the OmniShotCut pipeline.

    Small, serializable — no video data, no tensors, no full shot arrays.
    """

    status: str  # SUCCEEDED, FAILED
    video_id: str
    source_artifact_id: str = ""
    normalized_artifact_id: str = ""
    shots_artifact_id: str = ""
    normalized_artifact_uri: str = ""
    shots_artifact_uri: str = ""
    shot_count: int = 0
    runtime_ms: int = 0
    error_code: str = ""
    error_message: str = ""
    warnings: list[str] = field(default_factory=list)

    # Probe summary (small)
    probe_before: dict | None = None
    probe_after: dict | None = None
    ffmpeg_version: str = ""
    input_sha256: str = ""
    normalized_sha256: str = ""
    shots_sha256: str = ""

    # Keyframe extraction (optional)
    keyframes_artifact_uri: str = ""
    keyframes_artifact_id: str = ""
    keyframe_image_count: int = 0


# ---------------------------------------------------------------------------
# Pipeline Service
# ---------------------------------------------------------------------------


def run_omnishotcut_pipeline(
    *,
    video_id: str,
    source_video_path: Path,
    source_artifact_id: str | None = None,
    output_root: Path,
    mode: str = "clean_shot",
    extract_keyframes: bool = False,
) -> PipelineResult:
    """Run the complete OmniShotCut pipeline locally.

    Steps:
      1. Validate input
      2. FFprobe source → probe_before.json
      3. FFmpeg normalize → normalized.mp4
      4. FFprobe normalized → probe_after.json
      5. Validate normalization
      6. Write normalized_video artifacts + manifest
      7. Load OmniShotCut model
      8. Run inference (reading normalized.mp4 only)
      9. Convert + validate shots
     10. Write shots artifacts + manifest
     10.5 [if extract_keyframes] Extract keyframes via PyAV
     11. Return PipelineResult

    Args:
        video_id: Unique video identifier.
        source_video_path: Path to the source video file.
        source_artifact_id: Optional upstream artifact ID for lineage.
        output_root: Root directory for artifacts.
        mode: OmniShotCut inference mode (default: "clean_shot").
        extract_keyframes: If True, extract 25%, 50%, 75% keyframes
            per shot after shot detection (default: False).

    Returns:
        PipelineResult — small, no binary data.
    """
    t_start = time.monotonic()
    result = PipelineResult(
        status="FAILED",
        video_id=video_id,
        source_artifact_id=source_artifact_id or _new_id(),
    )

    # --- 1. Validate input ---
    if not source_video_path.exists():
        result.error_code = "SOURCE_NOT_FOUND"
        result.error_message = f"Source video not found: {source_video_path}"
        return result

    result.input_sha256 = _sha256_file(source_video_path)

    # --- Derive output paths ---
    project_id = "local_validation"
    norm_version = "1.0.0"
    model_version = "0.1.0"

    norm_dir = (
        output_root
        / "projects"
        / project_id
        / "videos"
        / video_id
        / "artifacts"
        / "video_normalization"
        / norm_version
    )
    shot_dir = (
        output_root
        / "projects"
        / project_id
        / "videos"
        / video_id
        / "artifacts"
        / "omnishotcut"
        / model_version
    )

    norm_dir.mkdir(parents=True, exist_ok=True)
    shot_dir.mkdir(parents=True, exist_ok=True)

    normalized_path = norm_dir / "normalized.mp4"
    writer = ArtifactWriter(str(output_root))

    # --- 2. FFprobe source (in-memory only, written later via ArtifactWriter) ---
    try:
        probe_before = run_ffprobe(str(source_video_path))
    except FFprobeError as e:
        result.error_code = "VIDEO_PROBE_FAILED"
        result.error_message = str(e)
        return result

    result.probe_before = probe_before.to_dict()

    # --- 3-4. Normalize video (probe→ffmpeg→probe) ---
    config = NormalizationConfig()
    cmd = build_normalize_command(
        input_path=str(source_video_path),
        output_path=str(normalized_path),
        probe=probe_before,
        config=config,
    )
    result.ffmpeg_version = get_ffmpeg_version()

    try:
        run_ffmpeg(cmd, timeout=3600, description="video normalization")
    except FFmpegError as e:
        result.error_code = "VIDEO_NORMALIZATION_FAILED"
        result.error_message = str(e)
        return result

    if not normalized_path.exists():
        result.error_code = "VIDEO_NORMALIZATION_FAILED"
        result.error_message = "FFmpeg reported success but output file missing"
        return result

    # --- 4. FFprobe normalized (in-memory) ---
    try:
        probe_after = run_ffprobe(str(normalized_path))
    except FFprobeError as e:
        result.error_code = "VIDEO_PROBE_FAILED"
        result.error_message = f"Probe after normalization failed: {e}"
        return result

    result.probe_after = probe_after.to_dict()

    # --- 5. Validate normalization ---
    validation_errors = validate_normalization(
        probe_before=probe_before,
        probe_after=probe_after,
        output_path=str(normalized_path),
        config=config,
    )
    if validation_errors:
        result.error_code = "NORMALIZED_VIDEO_VALIDATION_FAILED"
        result.error_message = "; ".join(validation_errors)
        return result

    result.normalized_sha256 = _sha256_file(normalized_path)

    # --- 6. Write normalized_video artifact (manifest only, video on disk) ---
    norm_artifact_id = _new_id()
    norm_rel = str(norm_dir.relative_to(output_root))
    producer_norm = ArtifactProducer(
        model_name="ffmpeg_normalizer",
        model_version=norm_version,
    )

    # Video already on disk from FFmpeg step — just write its manifest
    norm_size = normalized_path.stat().st_size
    writer.write_json_artifact(
        relative_path=f"{norm_rel}/normalized.mp4.meta.json",
        data={
            "file": "normalized.mp4",
            "artifact_id": norm_artifact_id,
            "artifact_type": "normalized_video",
            "sha256": result.normalized_sha256,
            "size_bytes": norm_size,
        },
        artifact_type="normalized_video",
        artifact_id=norm_artifact_id,
        video_id=video_id,
        run_id=_new_id(),
        producer=producer_norm,
        schema_version="1.0",
    )

    # Write probe artifacts (via JSON, not file re-read)
    writer.write_json_artifact(
        relative_path=f"{norm_rel}/probe_before.json",
        data=probe_before.to_dict(),
        artifact_type="probe_before",
        artifact_id=_new_id(),
        video_id=video_id,
        run_id=_new_id(),
        producer=producer_norm,
        schema_version="1.0",
    )
    writer.write_json_artifact(
        relative_path=f"{norm_rel}/probe_after.json",
        data=probe_after.to_dict(),
        artifact_type="probe_after",
        artifact_id=_new_id(),
        video_id=video_id,
        run_id=_new_id(),
        producer=producer_norm,
        schema_version="1.0",
    )

    normalize_manifest_path = norm_dir / "normalized_video.manifest.json"
    _write_manifest(
        normalize_manifest_path,
        {
            "schema_version": "1.0",
            "artifact_type": "normalized_video",
            "artifact_id": norm_artifact_id,
            "video_id": video_id,
            "source_artifact_id": result.source_artifact_id,
            "producer": {
                "name": "ffmpeg_normalizer",
                "version": norm_version,
                "ffmpeg_version": result.ffmpeg_version,
            },
            "normalization": {
                "container": config.container,
                "video_codec": config.video_codec,
                "pixel_format": config.pixel_format,
                "frame_rate_mode": config.frame_rate_mode,
                "audio_codec": config.audio_codec,
                "audio_sample_rate": config.audio_sample_rate,
            },
            "input": {
                "uri": str(source_video_path),
                "sha256": result.input_sha256,
            },
            "output": {
                "uri": str(normalized_path),
                "sha256": result.normalized_sha256,
                "size_bytes": normalized_path.stat().st_size,
            },
            "probe_before_uri": str(norm_dir / "probe_before.json"),
            "probe_after_uri": str(norm_dir / "probe_after.json"),
            "input_fps": {
                "fps_num": probe_before.fps_num,
                "fps_den": probe_before.fps_den,
                "frame_rate_mode": probe_before.frame_rate_mode,
            },
            "output_fps": {
                "fps_num": probe_after.fps_num,
                "fps_den": probe_after.fps_den,
            },
            "duration_delta_ms": abs(probe_before.duration_ms - probe_after.duration_ms),
            "validation_passed": True,
            "validation_errors": [],
        },
    )

    result.normalized_artifact_id = norm_artifact_id
    result.normalized_artifact_uri = str(normalized_path)

    # --- 7-8. OmniShotCut inference ---
    try:
        from models.omnishotcut.adapter import OmniShotCutAdapter

        adapter = OmniShotCutAdapter()
        adapter.load()
    except Exception as e:
        result.error_code = "OMNISHOTCUT_LOAD_FAILED"
        result.error_message = str(e)
        return result

    # Must use normalized.mp4, NOT the original video (§14)
    model_input = {
        "schema_version": "1.0",
        "task_id": f"local_{video_id}",
        "video_id": video_id,
        "model": {"name": "omnishotcut", "version": model_version},
        "input": {"video_uri": str(normalized_path)},
        "parameters": {"mode": mode},
    }

    t_inference = time.monotonic()
    try:
        output = adapter.predict(model_input)
    except Exception as e:
        result.error_code = "OMNISHOTCUT_INFERENCE_FAILED"
        result.error_message = str(e)
        return result

    inference_ms = int((time.monotonic() - t_inference) * 1000)

    if output.get("status") == "FAILED":
        err = output.get("error", {})
        result.error_code = err.get("code", "OMNISHOTCUT_INFERENCE_FAILED")
        result.error_message = err.get("message", "Unknown inference error")
        return result

    # --- 9. Extract shots from adapter ---
    shots_list = adapter._last_shots
    result.shot_count = len(shots_list)

    if not shots_list:
        result.error_code = "NO_SHOTS_DETECTED"
        result.error_message = "Model returned zero shots"
        return result

    # --- 10. Write shots artifacts ---
    shot_artifact_id = _new_id()
    shot_rel = str(shot_dir.relative_to(output_root))
    producer_shot = ArtifactProducer(
        model_name="omnishotcut",
        model_version=model_version,
        code_revision="23ad6fb",
    )

    shots_data = {
        "video_id": video_id,
        "model": {"name": "omnishotcut", "version": model_version},
        "shots": shots_list,
    }

    shot_manifest = writer.write_json_artifact(
        relative_path=f"{shot_rel}/shots.json",
        data=shots_data,
        artifact_type="shot_boundaries",
        artifact_id=shot_artifact_id,
        video_id=video_id,
        run_id=_new_id(),
        producer=producer_shot,
        schema_version="1.0",
    )

    # Save raw inference data separately
    raw_output = {
        "video_id": video_id,
        "mode": mode,
        "shot_count": result.shot_count,
        "inference_ms": inference_ms,
        "metrics": output.get("metrics", {}),
    }
    _write_json_atomic(shot_dir / "omnishotcut.raw.json", raw_output)

    result.shots_artifact_id = shot_artifact_id
    result.shots_artifact_uri = str(shot_dir / "shots.json")
    result.shots_sha256 = shot_manifest.output.sha256

    # --- 10.5. Extract keyframes (optional) ---
    if extract_keyframes:
        print("  [Keyframes] Extracting 25%/50%/75% keyframes per shot ...")
        try:
            import os as _os

            from pipelines.services.keyframe_service import run_keyframe_extraction

            storage_root = str(output_root)
            normalized_path = _os.path.join(
                storage_root,
                "projects",
                project_id,
                "videos",
                video_id,
                "artifacts",
                "video_normalization",
                "1.0.0",
                "normalized.mp4",
            )

            keyframe_result = run_keyframe_extraction(
                video_path=normalized_path,
                shots_data=shots_data,
                fps_num=probe_after.fps_num,
                fps_den=probe_after.fps_den,
                frame_count=probe_after.frame_count,
                video_width=probe_after.width,
                video_height=probe_after.height,
                shots_artifact_id=result.shots_artifact_id,
                normalized_video_artifact_id=result.normalized_artifact_id,
                video_id=video_id,
                run_id=_new_id(),
                output_root=storage_root,
            )

            if keyframe_result.status == "SUCCEEDED":
                result.keyframes_artifact_id = keyframe_result.summary_artifact_id
                result.keyframes_artifact_uri = keyframe_result.summary_artifact_uri
                result.keyframe_image_count = keyframe_result.unique_image_count
                shot_count = keyframe_result.shot_count
                print(
                    f"  [Keyframes] Done: {keyframe_result.unique_image_count} "
                    f"images for {shot_count} shots "
                    f"({keyframe_result.runtime_ms}ms)"
                )
            else:
                result.warnings.append(
                    f"Keyframe extraction failed: "
                    f"[{keyframe_result.error_code}] {keyframe_result.error_message}"
                )
                print(f"  [Keyframes] FAILED: {keyframe_result.error_message}")
        except Exception as e:
            result.warnings.append(f"Keyframe extraction error: {e}")
            print(f"  [Keyframes] FAILED: {e}")

    # --- 11. Finalize ---
    result.status = "SUCCEEDED"
    result.runtime_ms = int((time.monotonic() - t_start) * 1000)
    result.warnings = output.get("warnings", [])

    return result


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _new_id() -> str:
    return uuid.uuid4().hex[:16]


def _sha256_file(path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(8192), b""):
            h.update(chunk)
    return h.hexdigest()


def _save_probe_json(path: Path, probe: FFprobeResult) -> None:
    _write_json_atomic(path, probe.to_dict())


def _write_json_atomic(path: Path, data: dict) -> None:
    tmp = path.with_suffix(path.suffix + ".tmp")
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False, default=str)
    tmp.replace(path)


def _write_manifest(path: Path, data: dict) -> None:
    from datetime import datetime, timezone

    data["created_at"] = datetime.now(timezone.utc).isoformat()
    _write_json_atomic(path, data)
