"""Task schema — task lifecycle and status tracking."""

from datetime import datetime
from enum import Enum
from typing import Literal

from pydantic import BaseModel, Field, model_validator


class TaskStatus(str, Enum):
    PENDING = "PENDING"
    QUEUED = "QUEUED"
    RUNNING = "RUNNING"
    SUCCEEDED = "SUCCEEDED"
    FAILED = "FAILED"
    CANCELLED = "CANCELLED"
    SKIPPED = "SKIPPED"
    RETRYING = "RETRYING"
    INTERRUPTED = "INTERRUPTED"


class Task(BaseModel):
    """Tracks the full lifecycle of an async pipeline task."""

    task_id: str = Field(..., description="Unique task identifier")
    video_id: str = Field(..., description="Associated video")
    task_type: str = Field(
        default="full_video_analysis",
        description="Type of task (e.g. full_video_analysis)",
    )
    status: TaskStatus = Field(default=TaskStatus.PENDING)
    stage: str | None = Field(
        default=None,
        description="Current pipeline stage (e.g. detect_shots)",
    )
    progress: int = Field(default=0, ge=0, le=100, description="Progress percentage")
    created_at: datetime = Field(default_factory=datetime.utcnow)
    started_at: datetime | None = None
    finished_at: datetime | None = None
    error: str | None = Field(default=None, description="Error message if failed")
    retry_of_task_id: str | None = None
    retry_count: int = Field(default=0, ge=0)


class AnalysisTaskRequest(BaseModel):
    """Validated parameters for the in-process video analysis Workflow."""

    scene_analysis: bool = True
    score_mode: Literal["location_only", "character_only", "subtitle_only", "custom"] = (
        "location_only"
    )
    cut_intensity: Literal["high", "medium", "low"] = "medium"
    min_distance_s: int = Field(default=12, ge=0, le=3600)
    location_weight: int = Field(default=1, ge=0, le=10)
    character_weight: int = Field(default=1, ge=0, le=10)
    subtitle_weight: int = Field(default=1, ge=0, le=10)
    force_recompute: list[
        Literal[
            "normalize",
            "shots",
            "keyframes",
            "vision",
            "asr",
            "subtitle_semantic",
        ]
    ] = Field(default_factory=list)

    @model_validator(mode="after")
    def validate_custom_weights(self) -> "AnalysisTaskRequest":
        if (
            self.score_mode == "custom"
            and self.location_weight + self.character_weight + self.subtitle_weight == 0
        ):
            raise ValueError("custom score weights must contain at least one non-zero value")
        self.force_recompute = list(dict.fromkeys(self.force_recompute))
        return self
