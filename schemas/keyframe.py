"""Keyframe extraction schemas.

Defines the Pydantic models for keyframe samples, per-shot keyframe
groups, and the top-level keyframe summary artifact.

Per CLAUDE.md §5: all cross-module data uses schemas/ Pydantic models.
"""

from pydantic import BaseModel, Field

# ---------------------------------------------------------------------------
# Sample — one extracted frame
# ---------------------------------------------------------------------------


class KeyframeSample(BaseModel):
    """A single extracted keyframe within a shot."""

    position_num: int = Field(
        ..., ge=0, description="Numerator of position fraction (1=25%, 1=50%, 3=75%)"
    )
    position_den: int = Field(..., ge=1, description="Denominator of position fraction")
    frame_number: int = Field(..., ge=0, description="Absolute frame number in normalized video")
    timestamp_ms: int = Field(..., ge=0, description="Timestamp in milliseconds")
    decoded_pts_ms: int | None = Field(
        default=None, ge=0, description="PTS from decoder (validation)"
    )
    uri: str = Field(..., description="storage:// URI to the image file")
    sha256: str = Field(..., description="SHA-256 hex digest of image bytes")
    size_bytes: int = Field(..., ge=0, description="Image file size in bytes")
    duplicated_reference: bool = Field(
        default=False, description="True if this sample shares an image with another sample"
    )


# ---------------------------------------------------------------------------
# Per-shot group
# ---------------------------------------------------------------------------


class ShotKeyframes(BaseModel):
    """Keyframe samples for a single shot. Always contains 3 entries."""

    shot_id: str = Field(..., description="Shot identifier (e.g. shot_000001)")
    index: int = Field(..., ge=0, description="Zero-based shot index")
    start_ms: int = Field(..., ge=0, description="Shot start time in ms")
    end_ms: int = Field(..., ge=0, description="Shot end time in ms (exclusive)")
    samples: list[KeyframeSample] = Field(
        ...,
        min_length=1,
        max_length=3,
        description="1-3 keyframe samples (always 3 requested; dedup may reduce unique count)",
    )


# ---------------------------------------------------------------------------
# Top-level summary artifact
# ---------------------------------------------------------------------------


class KeyframeSummary(BaseModel):
    """Top-level keyframe artifact — written as keyframes.json."""

    schema_version: str = Field(default="1.0", description="Schema version")
    video_id: str = Field(..., description="Video identifier")
    producer: dict = Field(
        ..., description="{name, version, backend, pyav_version, ffmpeg_version}"
    )
    source: dict = Field(
        ...,
        description=(
            "{normalized_video_artifact_id, shots_artifact_id, fps_num, fps_den, frame_count}"
        ),
    )
    format: dict = Field(..., description="{encoding, quality, max_long_side, width, height}")
    shots: list[ShotKeyframes] = Field(default_factory=list, description="Per-shot keyframe groups")
    metrics: dict = Field(
        default_factory=dict,
        description=(
            "{shot_count, requested_sample_count, unique_image_count, "
            "deduplicated_sample_count, total_bytes, runtime_ms}"
        ),
    )
