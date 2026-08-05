"""Keyframe extraction — single-pass PyAV decode + JPEG/PNG encode.

Pure media logic with no database or storage knowledge.
Called by pipelines/services/keyframe_service.py and Celery tasks.

Algorithm:
  1. Compute target frames per shot (25%, 50%, 75% positions)
  2. Global dedup + sort by frame_number
  3. PyAV single-pass sequential decode
  4. Hit target frame → resize → encode → atomic write
  5. PTS validation against expected timestamp

All frame arithmetic uses integer math (no round(), no floats for positions).
"""

from __future__ import annotations

import hashlib
import io
import time
from dataclasses import dataclass, field
from pathlib import Path

import av
from PIL import Image

# ---------------------------------------------------------------------------
# Position constants — stored as fractions to avoid float imprecision
# ---------------------------------------------------------------------------

POSITIONS: tuple[tuple[int, int], ...] = (
    (1, 4),  # 25% — start-of-shot (used by VLM as img_1)
    (3, 4),  # 75% — end-of-shot (used by VLM as img_3)
)


# ---------------------------------------------------------------------------
# Data types
# ---------------------------------------------------------------------------


@dataclass
class KeyframeTarget:
    """One frame to extract from the video."""

    frame_number: int
    timestamp_ms: int
    shot_id: str
    position_num: int
    position_den: int
    filename: str
    # Set after extraction
    saved: bool = False
    sha256: str = ""
    size_bytes: int = 0
    decoded_pts_ms: int | None = None


@dataclass
class ExtractionResult:
    """Result of a keyframe extraction run."""

    saved: list[KeyframeTarget] = field(default_factory=list)
    not_found: list[KeyframeTarget] = field(default_factory=list)
    runtime_ms: int = 0
    total_bytes: int = 0


# ---------------------------------------------------------------------------
# Target frame computation (integer arithmetic)
# ---------------------------------------------------------------------------


def select_frame(
    start_frame: int,
    end_frame_exclusive: int,
    numerator: int,
    denominator: int,
) -> int:
    """Compute the target frame number for a given position fraction.

    Uses integer arithmetic — no round(), no floats for positions.

    Parameters
    ----------
    start_frame : int
        First frame of the shot (inclusive).
    end_frame_exclusive : int
        First frame after the shot (exclusive).
    numerator : int
        Position numerator (1, 1, 3 for 25%/50%/75%).
    denominator : int
        Position denominator (4, 2, 4).

    Returns
    -------
    int
        Target frame number, clamped to [start_frame, end_frame_exclusive - 1].

    Raises
    ------
    ValueError
        If the shot frame range is invalid (span <= 0).
    """
    span = end_frame_exclusive - start_frame
    if span <= 0:
        raise ValueError(
            f"Invalid shot frame range: "
            f"start_frame={start_frame}, end_frame_exclusive={end_frame_exclusive}"
        )

    max_offset = span - 1
    # Integer rounding: (numerator * max_offset + denominator // 2) // denominator
    offset = (numerator * max_offset + denominator // 2) // denominator

    return min(start_frame + offset, end_frame_exclusive - 1)


def frame_to_timestamp_ms(frame: int, fps_num: int, fps_den: int) -> int:
    """Convert a frame number to timestamp in milliseconds.

    Uses integer arithmetic: (frame * fps_den * 1000 + fps_num // 2) // fps_num
    """
    return (frame * fps_den * 1000 + fps_num // 2) // fps_num


# ---------------------------------------------------------------------------
# Target computation (per-shot → global sorted list)
# ---------------------------------------------------------------------------


def compute_keyframe_targets(
    shots: list[dict],
    fps_num: int,
    fps_den: int,
) -> list[KeyframeTarget]:
    """Compute all target frames from shot boundaries.

    Deduplicates globally: if two shots share a target frame, only one
    image is encoded. Each ShotKeyframes entry in the summary file may
    still reference the same URI for display purposes.

    Parameters
    ----------
    shots : list[dict]
        Shot records. Each must have shot_id, index, start_frame,
        end_frame_exclusive, start_ms, end_ms.
    fps_num : int
        FPS numerator (e.g. 24000 for 23.976).
    fps_den : int
        FPS denominator (e.g. 1001 for 23.976).

    Returns
    -------
    list[KeyframeTarget]
        Sorted by frame_number, globally deduplicated.
    """
    # Phase 1: compute raw targets
    raw: list[KeyframeTarget] = []
    seen_frames: set[int] = set()

    for s in shots:
        start = s.get("start_frame")
        end = s.get("end_frame_exclusive")

        if start is None or end is None:
            raise ValueError(
                f"Shot {s.get('shot_id', '?')} is missing frame fields. "
                f"Ensure the ShotConverter has populated start_frame / end_frame_exclusive."
            )

        for num, den in POSITIONS:
            frame = select_frame(start, end, num, den)
            ts = frame_to_timestamp_ms(frame, fps_num, fps_den)

            filename = f"{s['shot_id']}_{num:03d}_{den:03d}.jpg"

            target = KeyframeTarget(
                frame_number=frame,
                timestamp_ms=ts,
                shot_id=s["shot_id"],
                position_num=num,
                position_den=den,
                filename=filename,
            )
            raw.append(target)

    # Phase 2: global dedup — keep only first target per frame_number
    targets: list[KeyframeTarget] = []
    for t in raw:
        if t.frame_number not in seen_frames:
            seen_frames.add(t.frame_number)
            targets.append(t)

    # Phase 3: sort by frame_number
    targets.sort(key=lambda t: t.frame_number)

    return targets


# ---------------------------------------------------------------------------
# PyAV single-pass extraction
# ---------------------------------------------------------------------------


def extract_keyframes(
    video_path: str,
    targets: list[KeyframeTarget],
    output_dir: Path,
    image_format: str = "jpeg",
    quality: int = 85,
    max_long_side: int = 672,
) -> ExtractionResult:
    """Extract keyframes from video in a single sequential decode pass.

    Targets MUST be sorted by frame_number (ascending) before calling.

    Parameters
    ----------
    video_path : str
        Path to the normalized video file.
    targets : list[KeyframeTarget]
        Target frames to extract (sorted by frame_number).
    output_dir : Path
        Directory to write image files into.
    image_format : str
        "jpeg" or "png".
    quality : int
        JPEG quality 1-100 (ignored for PNG).
    max_long_side : int
        Resize so the longer side does not exceed this (preserves aspect ratio).

    Returns
    -------
    ExtractionResult
        {saved, not_found, runtime_ms, total_bytes}
    """
    t_start = time.monotonic()
    result = ExtractionResult()
    output_dir.mkdir(parents=True, exist_ok=True)

    if not targets:
        result.runtime_ms = int((time.monotonic() - t_start) * 1000)
        return result

    # Build frame_number → target lookups
    frame_targets: dict[int, list[KeyframeTarget]] = {}
    for t in targets:
        frame_targets.setdefault(t.frame_number, []).append(t)

    next_idx = 0
    total_targets = len(targets)

    container = av.open(video_path)
    try:
        stream = container.streams.video[0]
        stream.thread_type = "AUTO"

        time_base = float(stream.time_base) if stream.time_base else 0.0
        fps_num = int(stream.average_rate.numerator) if stream.average_rate else None
        fps_den = int(stream.average_rate.denominator) if stream.average_rate else None

        # Compute frame duration for PTS tolerance
        frame_duration_ms = (
            int((fps_den * 1000 + fps_num // 2) // fps_num)
            if fps_num and fps_den
            else 42  # ~24fps default
        )

        for decoded_index, frame in enumerate(container.decode(stream)):
            # Process all targets at this frame number
            if decoded_index in frame_targets:
                for target in frame_targets[decoded_index]:
                    _save_target(
                        frame=frame,
                        target=target,
                        output_dir=output_dir,
                        image_format=image_format,
                        quality=quality,
                        max_long_side=max_long_side,
                        time_base=time_base,
                        frame_duration_ms=frame_duration_ms,
                    )
                    result.saved.append(target)
                next_idx += len(frame_targets[decoded_index])

            # Early exit: all targets have been processed
            if next_idx >= total_targets:
                break

    finally:
        container.close()

    # Identify missed targets
    saved_frames = {t.frame_number for t in result.saved}
    for t in targets:
        if t.frame_number not in saved_frames:
            result.not_found.append(t)

    result.total_bytes = sum(t.size_bytes for t in result.saved)
    result.runtime_ms = int((time.monotonic() - t_start) * 1000)
    return result


# ---------------------------------------------------------------------------
# Internal: encode and write a single frame
# ---------------------------------------------------------------------------


def _save_target(
    frame: av.VideoFrame,
    target: KeyframeTarget,
    output_dir: Path,
    image_format: str,
    quality: int,
    max_long_side: int,
    time_base: float,
    frame_duration_ms: int,
) -> None:
    """Encode a PyAV frame to JPEG/PNG, resize, and atomic-write."""

    # PTS validation
    pts = frame.pts
    if pts is not None:
        decoded_pts_ms = round(int(pts) * time_base * 1000)
        target.decoded_pts_ms = decoded_pts_ms

        # Log mismatches but continue (CFR normalization should prevent these)
        if abs(decoded_pts_ms - target.timestamp_ms) > frame_duration_ms:
            import structlog

            _log = structlog.get_logger(__name__)
            _log.warning(
                "pts_mismatch",
                expected_ms=target.timestamp_ms,
                decoded_ms=decoded_pts_ms,
                frame_number=target.frame_number,
                shot_id=target.shot_id,
            )

    # Convert to PIL image
    img = frame.to_image()

    # Resize preserving aspect ratio
    w, h = img.size
    long_side = max(w, h)
    if long_side > max_long_side:
        scale = max_long_side / long_side
        new_size = (round(w * scale), round(h * scale))
        img = img.resize(new_size, Image.LANCZOS)  # type: ignore[attr-defined]

    # Encode to bytes (no EXIF metadata)
    buf = io.BytesIO()
    save_kwargs: dict = {}
    if image_format == "jpeg":
        save_kwargs["quality"] = quality

    # Pillow format string
    pil_format = "JPEG" if image_format == "jpeg" else "PNG"
    img.save(buf, format=pil_format, **save_kwargs)
    data = buf.getvalue()

    # Atomic write: temp → rename
    tmp_path = output_dir / (target.filename + ".tmp")
    final_path = output_dir / target.filename
    tmp_path.write_bytes(data)

    # Compute SHA-256
    target.sha256 = hashlib.sha256(data).hexdigest()
    target.size_bytes = len(data)
    target.saved = True

    tmp_path.replace(final_path)
