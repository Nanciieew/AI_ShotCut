"""Shot schema — a single continuous camera take."""

from typing import Optional

from pydantic import BaseModel, Field


class Shot(BaseModel):
    """One shot (continuous camera recording) within a video.

    Time range: [start_ms, end_ms) — includes start, excludes end.
    """

    shot_id: str = Field(..., description="Unique shot identifier, e.g. shot_000001")
    video_id: str = Field(..., description="Associated video")
    index: int = Field(..., ge=0, description="Zero-based shot index within the video")
    start_ms: int = Field(..., ge=0, description="Start time in milliseconds")
    end_ms: int = Field(..., ge=0, description="End time in milliseconds (exclusive)")
    start_frame: Optional[int] = Field(
        default=None, ge=0, description="Start frame number"
    )
    end_frame_exclusive: Optional[int] = Field(
        default=None, ge=0, description="End frame number (exclusive)"
    )
    boundary_type: Optional[str] = Field(
        default=None, description="Transition type: hard_cut, dissolve, wipe, etc."
    )
    confidence: Optional[float] = Field(
        default=None, ge=0.0, le=1.0, description="Detection confidence [0, 1]"
    )
