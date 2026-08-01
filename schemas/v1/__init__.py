"""Schema v1 — current production schema version.

All current schemas are v1. When breaking changes occur, v2/ will
be created alongside v1/ for backward compatibility.
"""

# Re-export all current schemas as v1
from schemas.artifact import Artifact
from schemas.model_run import ModelRun, ModelRunStatus
from schemas.result import FinalResult
from schemas.scene import Scene, SceneEvidence
from schemas.shot import Shot
from schemas.subtitle import SubtitleSegment
from schemas.task import Task, TaskStatus
from schemas.video import Video

SCHEMA_VERSION = "1.0"

__all__ = [
    "SCHEMA_VERSION",
    "Video",
    "Task",
    "TaskStatus",
    "ModelRun",
    "ModelRunStatus",
    "Artifact",
    "Shot",
    "SubtitleSegment",
    "Scene",
    "SceneEvidence",
    "FinalResult",
]
