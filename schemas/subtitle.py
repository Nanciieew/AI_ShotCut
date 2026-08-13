"""Subtitle segment schema — a single timed subtitle entry."""

from pydantic import BaseModel, Field


class SubtitleSegment(BaseModel):
    """One subtitle / closed-caption segment with timing.

    Time range: [start_ms, end_ms).
    """

    subtitle_id: str = Field(..., description="Unique subtitle identifier, e.g. subtitle_000001")
    video_id: str = Field(..., description="Associated video")
    start_ms: int = Field(..., ge=0, description="Start time in milliseconds")
    end_ms: int = Field(..., ge=0, description="End time in milliseconds (exclusive)")
    text: str = Field(default="", description="Transcription or subtitle text")
    language: str | None = Field(default=None, description="Language code, e.g. zh, en")
    confidence: float | None = Field(
        default=None, ge=0.0, le=1.0, description="ASR confidence [0, 1]"
    )


class SubtitleBoundaryContinuity(BaseModel):
    """Narrative continuity inferred from subtitles at one shot boundary."""

    shot_id: str
    boundary_index: int = Field(..., ge=0)
    timestamp_ms: int = Field(..., ge=0)
    subtitle_continuity: float = Field(..., ge=0.0, le=1.0)
    discovery_sources: list[str] = Field(default_factory=list)
    discovery_reasons: list[str] = Field(default_factory=list)
    reason: str = ""


class SubtitleContinuityArtifact(BaseModel):
    """Canonical output of hierarchical subtitle semantic analysis."""

    video_id: str
    boundaries: list[SubtitleBoundaryContinuity] = Field(default_factory=list)
    analysis: dict = Field(default_factory=dict)
