"""Final result schema — the complete pipeline output."""

from pydantic import BaseModel, Field

from schemas.scene import Scene, SceneEvidence
from schemas.shot import Shot
from schemas.subtitle import SubtitleSegment
from schemas.video import Video


class FinalResult(BaseModel):
    """Top-level result returned after a full video analysis pipeline.

    Contains the complete analysis: video metadata, shots, scenes,
    scene scores, and all evidence.
    """

    schema_version: str = Field(default="1.0")
    video: Video
    shots: list[Shot] = Field(default_factory=list)
    subtitles: list[SubtitleSegment] = Field(default_factory=list)
    scenes: list[Scene] = Field(default_factory=list)
    scene_evidence: list[SceneEvidence] = Field(default_factory=list)
    result_uri: str | None = Field(
        default=None,
        description="Storage URI for the complete final_result.json artifact",
    )
