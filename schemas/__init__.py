"""Unified schema layer — all canonical data structures.

Schema modules:
- video: Video metadata
- task: Task lifecycle and status
- model_run: Model inference execution record
- artifact: Stored artifact index entry
- shot: Single continuous take
- subtitle: Timed subtitle segment
- scene: Scene with evidence and score
- result: Complete pipeline output
"""

from schemas.video import Video
from schemas.task import Task, TaskStatus
from schemas.model_run import ModelRun, ModelRunStatus
from schemas.artifact import Artifact
from schemas.shot import Shot
from schemas.subtitle import SubtitleSegment
from schemas.scene import Scene, SceneEvidence
from schemas.result import FinalResult

__all__ = [
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
