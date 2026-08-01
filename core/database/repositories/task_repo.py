"""
Task repository — synchronous CRUD for Celery workers.

All methods receive a SQLAlchemy Session and do NOT manage
transactions themselves (caller commits/rolls back).
"""

from datetime import datetime, timezone

from sqlalchemy.orm import Session

from core.database.models import Task


class TaskRepository:
    """Minimal sync repository for Task lifecycle operations."""

    def __init__(self, session: Session) -> None:
        self._session = session

    # ------------------------------------------------------------------
    # Create
    # ------------------------------------------------------------------

    def create(
        self,
        task_id: str,
        video_id: str,
        task_type: str = "full_video_analysis",
        celery_task_id: str | None = None,
    ) -> Task:
        task = Task(
            task_id=task_id,
            video_id=video_id,
            task_type=task_type,
            status="PENDING",
            stage=None,
            progress=0,
            celery_task_id=celery_task_id,
        )
        self._session.add(task)
        return task

    # ------------------------------------------------------------------
    # Read
    # ------------------------------------------------------------------

    def get(self, task_id: str) -> Task | None:
        return self._session.get(Task, task_id)

    # ------------------------------------------------------------------
    # Update
    # ------------------------------------------------------------------

    def update_status(self, task_id: str, status: str) -> Task | None:
        """Set task status + record timing.

        RUNNING → sets started_at.
        SUCCEEDED / FAILED / CANCELLED → sets finished_at.
        """
        task = self.get(task_id)
        if task is None:
            return None

        task.status = status
        now = datetime.now(timezone.utc)

        if status == "RUNNING" and task.started_at is None:
            task.started_at = now
        elif status in ("SUCCEEDED", "FAILED", "CANCELLED"):
            task.finished_at = now
            if status == "SUCCEEDED":
                task.progress = 100

        return task

    def update_progress(self, task_id: str, progress: int, stage: str | None = None) -> Task | None:
        """Update progress 0-100 and optional stage label."""
        task = self.get(task_id)
        if task is None:
            return None
        task.progress = max(0, min(100, progress))
        if stage is not None:
            task.stage = stage
        return task

    def set_error(self, task_id: str, error_code: str, error_message: str) -> Task | None:
        """Record error details on a failed task."""
        task = self.get(task_id)
        if task is None:
            return None
        task.error_code = error_code
        task.error_message = error_message
        task.status = "FAILED"
        task.finished_at = datetime.now(timezone.utc)
        return task

    def set_celery_id(self, task_id: str, celery_task_id: str) -> Task | None:
        """Bind the Celery-internal task ID after dispatch."""
        task = self.get(task_id)
        if task is None:
            return None
        task.celery_task_id = celery_task_id
        return task

    def increment_retry(self, task_id: str) -> Task | None:
        """Increment retry count and set status to RETRYING."""
        task = self.get(task_id)
        if task is None:
            return None
        task.retry_count = (task.retry_count or 0) + 1
        task.status = "RETRYING"
        return task
