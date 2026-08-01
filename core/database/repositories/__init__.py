"""
Synchronous repository layer for Celery worker data access.

Each repository wraps a SQLAlchemy Session and provides
minimal CRUD operations. Callers are responsible for
transaction management (commit / rollback).
"""

from core.database.repositories.artifact_repo import ArtifactRepository
from core.database.repositories.task_repo import TaskRepository
from core.database.repositories.video_repo import VideoRepository

__all__ = [
    "TaskRepository",
    "VideoRepository",
    "ArtifactRepository",
]
