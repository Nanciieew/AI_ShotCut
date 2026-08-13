"""Scene schema — a group of contiguous shots forming a narrative unit.

Also defines SceneEvidence, the ONLY allowed evidence types for
computing scene_score. action_score and plot_score are FORBIDDEN.
"""

from pydantic import BaseModel, Field


class SceneEvidence(BaseModel):
    """Continuity evidence for a scene boundary decision.

    All values in [0, 1] where 1.0 = strongest continuity.

    FORBIDDEN fields: action_score, plot_score, action_evidence, plot_evidence.
    """

    scene_id: str = Field(..., description="Associated scene")
    visual_continuity: float | None = Field(default=None, ge=0.0, le=1.0)
    character_continuity: float | None = Field(default=None, ge=0.0, le=1.0)
    location_continuity: float | None = Field(default=None, ge=0.0, le=1.0)
    subtitle_continuity: float | None = Field(default=None, ge=0.0, le=1.0)
    audio_continuity: float | None = Field(default=None, ge=0.0, le=1.0)
    temporal_gap_ms: int | None = Field(
        default=None, ge=0, description="Gap to previous scene in milliseconds"
    )


class Scene(BaseModel):
    """A scene composed of one or more contiguous shots.

    scene_score is the ONLY score concept in the system.
    """

    scene_id: str = Field(..., description="Unique scene identifier, e.g. scene_000001")
    video_id: str = Field(..., description="Associated video")
    index: int = Field(..., ge=0, description="Zero-based scene index within the video")
    start_ms: int = Field(..., ge=0, description="Start time in milliseconds")
    end_ms: int = Field(..., ge=0, description="End time in milliseconds (exclusive)")
    shot_ids: list[str] = Field(default_factory=list, description="Ordered shot IDs in this scene")
    boundary_confidence: float | None = Field(
        default=None, ge=0.0, le=1.0, description="Scene boundary detection confidence"
    )
    scene_score: float | None = Field(
        default=None,
        ge=0.0,
        le=1.0,
        description=(
            "Confidence that the Scene end is a true boundary. Null for the terminal Scene."
        ),
    )


class SceneBoundary(BaseModel):
    """A selected boundary closing the Scene identified by scene_id."""

    scene_id: str
    shot_id: str
    boundary_index: int = Field(..., ge=0)
    timestamp_ms: int = Field(..., ge=0)
    scene_score: float = Field(..., ge=0.0, le=1.0)
    location_continuity: float | None = Field(default=None, ge=0.0, le=1.0)
    character_continuity: float | None = Field(default=None, ge=0.0, le=1.0)
    subtitle_continuity: float | None = Field(default=None, ge=0.0, le=1.0)


class CandidateBoundary(BaseModel):
    """Persisted score and evidence for every boundary evaluated by one merge run."""

    candidate_id: str
    video_id: str
    producer_run_id: str
    shot_id: str
    scene_id: str | None = None
    boundary_index: int = Field(..., ge=0)
    timestamp_ms: int = Field(..., ge=0)
    scene_score: float = Field(..., ge=0.0, le=1.0)
    location_continuity: float | None = Field(default=None, ge=0.0, le=1.0)
    character_continuity: float | None = Field(default=None, ge=0.0, le=1.0)
    subtitle_continuity: float | None = Field(default=None, ge=0.0, le=1.0)
    selected: bool = False
    selection_rank: int | None = Field(default=None, ge=0)
