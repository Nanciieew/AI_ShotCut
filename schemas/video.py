"""Video schema — canonical representation of a video asset."""

from pydantic import BaseModel, Field


class Video(BaseModel):
    """Represents a video after upload and normalization.

    All time values in integer milliseconds.
    FPS stored as rational (num/den) to avoid floating-point drift.
    """

    video_id: str = Field(..., description="Unique video identifier, e.g. video_001")
    project_id: str = Field(..., description="Owning project ID")
    source_uri: str = Field(
        default="",
        description="URI of the original uploaded file",
    )
    normalized_uri: str = Field(
        default="",
        description="URI of the normalized MP4",
    )
    audio_uri: str = Field(
        default="",
        description="URI of the extracted audio (WAV, 16 kHz mono)",
    )
    duration_ms: int = Field(..., ge=0, description="Video duration in milliseconds")
    fps_num: int = Field(default=24000, description="FPS numerator")
    fps_den: int = Field(default=1001, description="FPS denominator")
    width: int = Field(default=1920, ge=1, description="Frame width in pixels")
    height: int = Field(default=1080, ge=1, description="Frame height in pixels")
    audio_sample_rate: int = Field(default=16000, description="Audio sample rate in Hz")
