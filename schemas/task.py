"""Task schema — task lifecycle and status tracking."""

from datetime import datetime
from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field


class TaskStatus(str, Enum):
    PENDING = "PENDING"
    QUEUED = "QUEUED"
    RUNNING = "RUNNING"
    SUCCEEDED = "SUCCEEDED"
    FAILED = "FAILED"
    CANCELLED = "CANCELLED"
    SKIPPED = "SKIPPED"
    RETRYING = "RETRYING"


class Task(BaseModel):
    """Tracks the full lifecycle of an async pipeline task."""

    task_id: str = Field(..., description="Unique task identifier")
    video_id: str = Field(..., description="Associated video")
    task_type: str = Field(
        default="full_video_analysis",
        description="Type of task (e.g. full_video_analysis)",
    )
    status: TaskStatus = Field(default=TaskStatus.PENDING)
    stage: Optional[str] = Field(
        default=None,
        description="Current pipeline stage (e.g. detect_shots)",
    )
    progress: int = Field(default=0, ge=0, le=100, description="Progress percentage")
    created_at: datetime = Field(default_factory=datetime.utcnow)
    started_at: Optional[datetime] = None
    finished_at: Optional[datetime] = None
    error: Optional[str] = Field(default=None, description="Error message if failed")
