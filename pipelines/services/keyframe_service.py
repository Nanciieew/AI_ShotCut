"""Keyframe extraction service — shared orchestration.

Called by both the Celery task (workers/tasks/keyframe_tasks.py) and
the local pipeline (pipelines/services/omnishotcut_pipeline.py).

Per CLAUDE.md §19: do NOT create separate local/Docker implementations.
"""

from __future__ import annotations

import json
import os
import time
import uuid
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

from core.artifacts.writer import ArtifactWriter
from core.artifacts import ArtifactProducer, ArtifactInputRef
from core.media.keyframes import (
    compute_keyframe_targets,
    extract_keyframes,
    KeyframeTarget,
    ExtractionResult,
)
from core.media.exceptions import KeyframeExtractionError


# ---------------------------------------------------------------------------
# Result type
# ---------------------------------------------------------------------------

@dataclass
class KeyframeServiceResult:
    """Result from the keyframe extraction service."""
    status: str  # "SUCCEEDED" | "FAILED"
    summary_artifact_id: str = ""
    summary_artifact_uri: str = ""
    summary_sha256: str = ""
    shot_count: int = 0
    unique_image_count: int = 0
    deduplicated_count: int = 0
    total_bytes: int = 0
    runtime_ms: int = 0
    error_code: str = ""
    error_message: str = ""
    raw_targets: list[KeyframeTarget] = field(default_factory=list)


# ---------------------------------------------------------------------------
# Service
# ---------------------------------------------------------------------------

def run_keyframe_extraction(
    *,
    video_path: str,
    shots_data: dict,
    fps_num: int,
    fps_den: int,
    frame_count: int,
    video_width: int,
    video_height: int,
    shots_artifact_id: str,
    normalized_video_artifact_id: str,
    video_id: str,
    run_id: str,
    output_root: str,
    image_format: str = "jpeg",
    quality: int = 85,
    max_long_side: int = 672,
) -> KeyframeServiceResult:
    """Extract keyframes for every shot and write the summary artifact.

    Parameters
    ----------
    video_path : str
        Absolute path to the normalized video file.
    shots_data : dict
        Parsed shots.json content (must contain "shots" list).
    fps_num, fps_den : int
        FPS as a rational number.
    frame_count : int
        Total frame count of the normalized video (from probe).
    video_width, video_height : int
        Pixel dimensions of the normalized video.
    shots_artifact_id : str
        Artifact ID of the input shots.json (for lineage).
    normalized_video_artifact_id : str
        Artifact ID of the normalized video (for lineage).
    video_id : str
        Video identifier.
    run_id : str
        ModelRun identifier for this extraction.
    output_root : str
        Storage root directory.
    image_format : str
        "jpeg" or "png".
    quality : int
        JPEG quality 1-100.
    max_long_side : int
        Maximum long-side pixel count for output images.

    Returns
    -------
    KeyframeServiceResult
    """
    t_start = time.monotonic()
    result = KeyframeServiceResult(status="FAILED")
    writer = ArtifactWriter(output_root)

    # --- 1. Compute targets ---
    shots_list = shots_data.get("shots", [])
    if not shots_list:
        result.error_code = "NO_SHOTS"
        result.error_message = "Shots data contains no shots"
        return result

    try:
        targets = compute_keyframe_targets(shots_list, fps_num, fps_den)
    except ValueError as e:
        result.error_code = "TARGET_COMPUTATION_FAILED"
        result.error_message = str(e)
        return result

    if not targets:
        result.error_code = "NO_TARGETS"
        result.error_message = "No keyframe targets computed (empty shot list?)"
        return result

    result.raw_targets = targets

    # --- 2. Extraction ---
    producer_name = "ffmpeg_keyframes"
    producer_version = "1.0.0"

    artifact_base = (
        f"projects/{{project}}/videos/{video_id}/"
        f"artifacts/{producer_name}/{producer_version}"
    )
    # Placeholder project — filled at write time
    relative_dir = artifact_base.format(project="_")
    # Actually build the real path
    # We need the project_id — extract from shots_data or use "default"
    project_id = "default"  # keyframe service uses default project
    artifact_base = (
        f"projects/{project_id}/videos/{video_id}/"
        f"artifacts/{producer_name}/{producer_version}"
    )

    images_dir = Path(output_root) / artifact_base / "images"
    images_dir.mkdir(parents=True, exist_ok=True)

    try:
        extraction = extract_keyframes(
            video_path=video_path,
            targets=targets,
            output_dir=images_dir,
            image_format=image_format,
            quality=quality,
            max_long_side=max_long_side,
        )
    except Exception as e:
        result.error_code = "EXTRACTION_FAILED"
        result.error_message = str(e)
        return result

    if extraction.not_found:
        # Some frames were not found — this should not happen with CFR video
        missed = [t.frame_number for t in extraction.not_found]
        raise KeyframeExtractionError(
            f"Frames not found during extraction: {missed[:10]}..."
            if len(missed) > 10
            else f"Frames not found during extraction: {missed}"
        )

    # --- 3. Build summary ---
    # Map targets back to shots for the summary
    shot_map: dict[str, list[KeyframeTarget]] = {}
    for t in extraction.saved:
        shot_map.setdefault(t.shot_id, []).append(t)

    # Detect duplicated references (targets that were deduped from raw)
    raw_per_shot: dict[str, list[dict]] = {}
    for s in shots_list:
        raw_per_shot[s["shot_id"]] = []
        start = s["start_frame"]
        end = s["end_frame_exclusive"]
        for num, den in [(1, 4), (1, 2), (3, 4)]:
            from core.media.keyframes import select_frame, frame_to_timestamp_ms
            fnum = select_frame(start, end, num, den)
            ts = frame_to_timestamp_ms(fnum, fps_num, fps_den)
            raw_per_shot[s["shot_id"]].append({
                "frame_number": fnum,
                "position_num": num,
                "position_den": den,
                "timestamp_ms": ts,
            })

    # Count deduped samples
    total_requested = len(shots_list) * 3
    unique_images = len(extraction.saved)

    shots_output: list[dict] = []
    for s in shots_list:
        shot_targets = shot_map.get(s["shot_id"], [])
        target_by_frame: dict[int, KeyframeTarget] = {
            t.frame_number: t for t in shot_targets
        }
        raw_samples = raw_per_shot.get(s["shot_id"], [])

        samples: list[dict] = []
        for raw in raw_samples:
            t = target_by_frame.get(raw["frame_number"])
            if t is not None:
                image_rel = f"{artifact_base}/images/{t.filename}"
                samples.append({
                    "position_num": raw["position_num"],
                    "position_den": raw["position_den"],
                    "frame_number": t.frame_number,
                    "timestamp_ms": t.timestamp_ms,
                    "decoded_pts_ms": t.decoded_pts_ms,
                    "uri": f"storage://{image_rel}",
                    "sha256": t.sha256,
                    "size_bytes": t.size_bytes,
                    "duplicated_reference": False,
                })
            else:
                # This sample was deduped — point to the closest saved target
                # (same frame_number was de-duplicated globally)
                # Find the target that was actually saved for this frame
                samples.append({
                    "position_num": raw["position_num"],
                    "position_den": raw["position_den"],
                    "frame_number": raw["frame_number"],
                    "timestamp_ms": raw["timestamp_ms"],
                    "decoded_pts_ms": None,
                    "uri": None,
                    "sha256": "",
                    "size_bytes": 0,
                    "duplicated_reference": True,
                    "note": "Frame not extracted (same frame as another sample, or decode miss)",
                })

        # Mark duplicates: when multiple samples share the same frame_number, only one is the "original"
        frame_uris: dict[int, str] = {}
        for smp in samples:
            fn = smp["frame_number"]
            if fn not in frame_uris and smp["uri"]:
                frame_uris[fn] = smp["uri"]
        for smp in samples:
            fn = smp["frame_number"]
            if smp["uri"] is None and fn in frame_uris:
                smp["uri"] = frame_uris[fn]
                # Copy sha256/size from a saved target
                for t in extraction.saved:
                    if t.frame_number == fn:
                        smp["sha256"] = t.sha256
                        smp["size_bytes"] = t.size_bytes
                        smp["decoded_pts_ms"] = t.decoded_pts_ms
                        break

        shots_output.append({
            "shot_id": s["shot_id"],
            "index": s.get("index", 0),
            "start_ms": s.get("start_ms", 0),
            "end_ms": s.get("end_ms", 0),
            "samples": samples,
        })

    # Count dedup
    dedup_count = sum(
        1 for shot in shots_output
        for smp in shot["samples"]
        if smp.get("duplicated_reference", False)
    )

    # --- 4. Write summary artifact ---
    import av as _av
    summary_data = {
        "schema_version": "1.0",
        "video_id": video_id,
        "producer": {
            "name": producer_name,
            "version": producer_version,
            "backend": "pyav",
            "pyav_version": _av.__version__,
        },
        "source": {
            "normalized_video_artifact_id": normalized_video_artifact_id,
            "shots_artifact_id": shots_artifact_id,
            "fps_num": fps_num,
            "fps_den": fps_den,
            "frame_count": frame_count,
        },
        "format": {
            "encoding": image_format,
            "quality": quality,
            "max_long_side": max_long_side,
            "width": video_width,
            "height": video_height,
        },
        "shots": shots_output,
        "metrics": {
            "shot_count": len(shots_list),
            "requested_sample_count": total_requested,
            "unique_image_count": unique_images,
            "deduplicated_sample_count": dedup_count,
            "total_bytes": extraction.total_bytes,
            "runtime_ms": extraction.runtime_ms,
        },
    }

    summary_rel = f"{artifact_base}/keyframes.json"

    producer = ArtifactProducer(
        model_name=producer_name,
        model_version=producer_version,
        code_revision="unknown",
        weight_revision="unknown",
    )

    input_ref = ArtifactInputRef(
        video_sha256="",
        input_artifact_uris=[
            f"storage://{artifact_base.format(project=project_id)}/../video_normalization/*/normalized.mp4",
        ],
    )

    manifest = writer.write_json_artifact(
        relative_path=summary_rel,
        data=summary_data,
        artifact_type="shot_keyframes",
        artifact_id=f"{run_id}_keyframes",
        video_id=video_id,
        run_id=run_id,
        producer=producer,
        input_ref=input_ref,
        schema_version="1.0",
    )

    result.status = "SUCCEEDED"
    result.summary_artifact_id = f"{run_id}_keyframes"
    result.summary_artifact_uri = f"storage://{summary_rel}"
    result.summary_sha256 = manifest.output.sha256
    result.shot_count = len(shots_list)
    result.unique_image_count = unique_images
    result.deduplicated_count = dedup_count
    result.total_bytes = extraction.total_bytes
    result.runtime_ms = extraction.runtime_ms

    return result
