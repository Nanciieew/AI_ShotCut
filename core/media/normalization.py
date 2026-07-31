"""Video normalization pipeline.

Orchestrates the complete normalization flow:
  1. FFprobe input video → probe_before.json
  2. FFmpeg re-encode → normalized.mp4
  3. FFprobe output → probe_after.json
  4. Validate output against spec
  5. Generate normalization manifest

All operations use temp files + atomic rename.
Original video is NEVER modified.
"""

import hashlib
import json
import os
import time
from pathlib import Path
from typing import Optional

from core.media.schemas import (
    FFprobeResult,
    NormalizationConfig,
    NormalizationResult,
)
from core.media.ffprobe import probe_video, run_ffprobe
from core.media.ffmpeg import build_normalize_command, run_ffmpeg, get_ffmpeg_version
from core.media.exceptions import (
    NormalizationError,
    NormalizationValidationError,
)


def normalize_video_file(
    input_path: str,
    output_dir: str,
    input_sha256: Optional[str] = None,
    config: Optional[NormalizationConfig] = None,
    ffmpeg_bin: str = "ffmpeg",
    ffprobe_bin: str = "ffprobe",
    ffmpeg_timeout: int = 600,
) -> NormalizationResult:
    """Normalize a video file to the project's standard format.

    Steps:
      1. Compute input SHA256 (if not provided)
      2. FFprobe input → probe_before.json
      3. FFmpeg normalize → normalized.mp4 (temp → atomic rename)
      4. FFprobe output → probe_after.json
      5. Validate output
      6. Generate manifest

    Args:
        input_path: Path to the source video file.
        output_dir: Directory to write normalized output + probes.
        input_sha256: Pre-computed SHA256 of input. Computed if absent.
        config: Normalization parameters. Uses default if omitted.
        ffmpeg_bin: Path to ffmpeg.
        ffprobe_bin: Path to ffprobe.
        ffmpeg_timeout: Max seconds for the ffmpeg encode.

    Returns:
        NormalizationResult with all paths, probes, and validation status.

    Raises:
        NormalizationError: If any step fails unrecoverably.
    """
    cfg = config or NormalizationConfig()

    if not os.path.exists(input_path):
        raise NormalizationError(f"Input video not found: {input_path}")

    os.makedirs(output_dir, exist_ok=True)

    # --- 1. Input SHA256 ---
    if input_sha256 is None:
        input_sha256 = _sha256_file(input_path)

    # --- 2. FFprobe input → probe_before.json ---
    try:
        probe_before = probe_video(
            input_path,
            output_dir=output_dir,
            label="probe_before",
            ffprobe_bin=ffprobe_bin,
        )
    except Exception as e:
        raise NormalizationError(f"FFprobe input failed: {e}") from e

    probe_before_path = os.path.join(output_dir, "probe_before.json")

    # --- 3. Build FFmpeg command ---
    output_tmp = os.path.join(output_dir, "normalized.mp4.tmp")
    output_final = os.path.join(output_dir, "normalized.mp4")

    cmd = build_normalize_command(
        input_path=input_path,
        output_path=output_tmp,
        probe=probe_before,
        config=cfg,
    )

    ffmpeg_version = get_ffmpeg_version(ffmpeg_bin)

    # --- 4. Run FFmpeg ---
    t0 = time.monotonic()
    try:
        run_ffmpeg(cmd, timeout=ffmpeg_timeout, description="video normalization")
    except Exception as e:
        # Clean up temp file on failure
        _remove_if_exists(output_tmp)
        raise NormalizationError(f"FFmpeg normalization failed: {e}") from e

    runtime_ms = int((time.monotonic() - t0) * 1000)

    # Atomic rename temp → final
    if not os.path.exists(output_tmp):
        raise NormalizationError(
            f"FFmpeg reported success but output file not found: {output_tmp}"
        )
    os.rename(output_tmp, output_final)

    # --- 5. FFprobe output → probe_after.json ---
    try:
        probe_after = probe_video(
            output_final,
            output_dir=output_dir,
            label="probe_after",
            ffprobe_bin=ffprobe_bin,
        )
    except Exception as e:
        raise NormalizationError(f"FFprobe output failed: {e}") from e

    probe_after_path = os.path.join(output_dir, "probe_after.json")

    # --- 6. Validate ---
    output_sha256 = _sha256_file(output_final)
    output_size = os.path.getsize(output_final)
    duration_delta_ms = abs(probe_before.duration_ms - probe_after.duration_ms)

    validation_errors: list[str] = []

    # 6a. Video stream exists
    if not probe_after.has_video:
        validation_errors.append("No video stream in normalized output")

    # 6b. Codec readable
    if probe_after.video_codec == "unknown":
        validation_errors.append("Video codec unreadable in normalized output")

    # 6c. Duration reasonable (not zero, not wildly different)
    if probe_after.duration_ms <= 0:
        validation_errors.append(
            f"Normalized duration is {probe_after.duration_ms}ms (expected > 0)"
        )
    else:
        max_delta = max(cfg.max_duration_delta_ms, probe_before.duration_one_frame_ms)
        if duration_delta_ms > max_delta:
            validation_errors.append(
                f"Duration delta {duration_delta_ms}ms exceeds max {max_delta}ms"
            )

    # 6d. Frame count reasonable
    if probe_after.frame_count <= 0:
        validation_errors.append(
            f"Normalized frame count is {probe_after.frame_count} (expected > 0)"
        )

    # 6e. FPS reasonable
    if probe_after.fps_num <= 0 or probe_after.fps_den <= 0:
        validation_errors.append("Normalized FPS is invalid")

    # 6f. Timestamps from zero (or near zero)
    if abs(probe_after.start_time_ms) > 100:
        validation_errors.append(
            f"Start time {probe_after.start_time_ms}ms not near zero"
        )

    # 6g. Pixel format
    if probe_after.pixel_format != cfg.pixel_format:
        validation_errors.append(
            f"Pixel format {probe_after.pixel_format} != {cfg.pixel_format}"
        )

    # 6h. Container is mp4
    if "mp4" not in probe_after.container_format.lower():
        validation_errors.append(
            f"Container {probe_after.container_format} is not mp4"
        )

    # 6i. Output not empty
    if output_size == 0:
        validation_errors.append("Normalized output file is empty")

    # 6j. FFmpeg exit was success (already checked by run_ffmpeg, but double-check)
    if not os.path.exists(output_final):
        validation_errors.append("Normalized output file does not exist")

    validation_passed = len(validation_errors) == 0

    # --- 7. Write manifest ---
    manifest_path = os.path.join(output_dir, "normalized_video.manifest.json")
    manifest = _build_normalization_manifest(
        result=NormalizationResult(
            input_path=input_path,
            input_sha256=input_sha256,
            output_path=output_final,
            output_sha256=output_sha256,
            output_size_bytes=output_size,
            probe_before=probe_before,
            probe_before_path=probe_before_path,
            probe_after=probe_after,
            probe_after_path=probe_after_path,
            duration_delta_ms=duration_delta_ms,
            validation_passed=validation_passed,
            validation_errors=validation_errors,
            ffmpeg_version=ffmpeg_version,
            ffmpeg_command=cmd,
            runtime_ms=runtime_ms,
            manifest_path=manifest_path,
        ),
        config=cfg,
    )
    _write_json_atomic(manifest_path, manifest)

    return NormalizationResult(
        input_path=input_path,
        input_sha256=input_sha256,
        output_path=output_final,
        output_sha256=output_sha256,
        output_size_bytes=output_size,
        probe_before=probe_before,
        probe_before_path=probe_before_path,
        probe_after=probe_after,
        probe_after_path=probe_after_path,
        duration_delta_ms=duration_delta_ms,
        validation_passed=validation_passed,
        validation_errors=validation_errors,
        ffmpeg_version=ffmpeg_version,
        ffmpeg_command=cmd,
        runtime_ms=runtime_ms,
        manifest_path=manifest_path,
    )


def validate_normalization(
    probe_before: FFprobeResult,
    probe_after: FFprobeResult,
    output_path: str,
    config: Optional[NormalizationConfig] = None,
) -> list[str]:
    """Validate a completed normalization without re-running it.

    Returns a list of error strings (empty = valid).
    """
    cfg = config or NormalizationConfig()
    errors: list[str] = []

    if not os.path.exists(output_path):
        errors.append(f"Output file missing: {output_path}")
        return errors

    if os.path.getsize(output_path) == 0:
        errors.append("Output file is empty")

    if not probe_after.has_video:
        errors.append("No video stream")

    if probe_after.video_codec == "unknown":
        errors.append("Unreadable codec")

    if probe_after.duration_ms <= 0:
        errors.append("Invalid duration")

    delta = abs(probe_before.duration_ms - probe_after.duration_ms)
    max_delta = max(cfg.max_duration_delta_ms, probe_before.duration_one_frame_ms)
    if delta > max_delta:
        errors.append(f"Duration delta {delta}ms > {max_delta}ms")

    if probe_after.pixel_format != cfg.pixel_format:
        errors.append(f"Pixel format mismatch: {probe_after.pixel_format}")

    if "mp4" not in probe_after.container_format.lower():
        errors.append(f"Container not mp4: {probe_after.container_format}")

    return errors


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _sha256_file(path: str) -> str:
    """Compute SHA-256 hex digest of a file."""
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(8192), b""):
            h.update(chunk)
    return h.hexdigest()


def _remove_if_exists(path: str) -> None:
    """Remove a file if it exists, silently."""
    try:
        os.remove(path)
    except OSError:
        pass


def _write_json_atomic(path: str, data: dict) -> None:
    """Write JSON to a temp file then atomic rename."""
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False, default=str)
    os.replace(tmp, path)


def _build_normalization_manifest(
    result: NormalizationResult,
    config: NormalizationConfig,
) -> dict:
    """Build a normalization manifest dict per the document spec §9."""
    from datetime import datetime, timezone

    return {
        "schema_version": "1.0",
        "artifact_type": "normalized_video",
        "video_id": "",  # filled by caller
        "source_artifact_id": "",  # filled by caller
        "producer": {
            "name": "ffmpeg_normalizer",
            "version": "1.0.0",
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
            "uri": f"file://{result.input_path}",
            "sha256": result.input_sha256,
        },
        "output": {
            "uri": f"file://{result.output_path}",
            "sha256": result.output_sha256,
            "size_bytes": result.output_size_bytes,
        },
        "probe_before_uri": f"file://{result.probe_before_path}",
        "probe_after_uri": f"file://{result.probe_after_path}",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "duration_delta_ms": result.duration_delta_ms,
        "validation_passed": result.validation_passed,
        "validation_errors": result.validation_errors,
        "input_fps": {
            "fps_num": result.probe_before.fps_num,
            "fps_den": result.probe_before.fps_den,
            "frame_rate_mode": result.probe_before.frame_rate_mode,
        },
        "output_fps": {
            "fps_num": result.probe_after.fps_num,
            "fps_den": result.probe_after.fps_den,
        },
        "runtime_ms": result.runtime_ms,
    }
