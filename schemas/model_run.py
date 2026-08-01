"""ModelRun schema — record of a single model inference execution."""

from datetime import datetime
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field


class ModelRunStatus(str, Enum):
    PENDING = "PENDING"
    RUNNING = "RUNNING"
    SUCCEEDED = "SUCCEEDED"
    FAILED = "FAILED"


class ModelRun(BaseModel):
    """Immutable record of one model execution for reproducibility."""

    run_id: str = Field(..., description="Unique run identifier")
    task_id: str = Field(..., description="Parent pipeline task ID")
    video_id: str = Field(..., description="Associated video")
    model_name: str = Field(..., description="Model identifier, e.g. omnishotcut")
    model_version: str = Field(..., description="Pinned model version, e.g. 1.0.0")
    code_revision: str | None = Field(default=None, description="Git commit of the adapter code")
    weight_revision: str | None = Field(default=None, description="Checkpoint or weight identifier")
    schema_version: str = Field(default="1.0", description="Version of the I/O schema used")
    parameters: dict[str, Any] = Field(
        default_factory=dict, description="Model-specific parameters"
    )
    status: ModelRunStatus = Field(default=ModelRunStatus.PENDING)
    runtime_ms: int | None = Field(
        default=None, ge=0, description="Wall-clock runtime in milliseconds"
    )
    device: str | None = Field(default=None, description="Device used, e.g. cuda:0, cpu")

    # Lifecycle timestamps (populated by the Celery task runner)
    started_at: datetime | None = None
    finished_at: datetime | None = None
