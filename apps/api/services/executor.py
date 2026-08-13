"""BackgroundExecutor — controlled thread pool for Workflow execution.

Constraints:
- max_workers=2, single process MVP
- Same task_id cannot be submitted twice
- Records executor_run_id on Task
- Catches submit failures, marks Task FAILED
- Graceful shutdown on app close
"""

import logging
import uuid
from concurrent.futures import ThreadPoolExecutor

from core.database.models import Task as TaskModel
from core.database.session_sync import get_sync_session


def _new_id() -> str:
    return uuid.uuid4().hex


logger = logging.getLogger(__name__)


class BackgroundExecutor:
    """Controlled background executor for pipeline workflows."""

    def __init__(self, max_workers: int = 2):
        self._pool = ThreadPoolExecutor(max_workers=max_workers)
        self._running: dict[str, str] = {}

    def submit(self, tracking_task_id: str, fn, *args, **kwargs) -> str:
        """Submit a workflow. Returns executor_run_id."""
        if tracking_task_id in self._running:
            raise ValueError(f"Task {tracking_task_id} is already running")

        run_id = _new_id()
        self._running[tracking_task_id] = run_id

        # Record executor_run_id on Task
        with get_sync_session() as session:
            t = session.get(TaskModel, tracking_task_id)
            if t:
                t.executor_run_id = run_id
                t.status = "QUEUED"
                session.commit()

        try:
            self._pool.submit(
                self._wrap,
                tracking_task_id,
                run_id,
                fn,
                *args,
                **kwargs,
            )
        except Exception as e:
            self._running.pop(tracking_task_id, None)
            with get_sync_session() as session:
                t = session.get(TaskModel, tracking_task_id)
                if t:
                    t.status = "FAILED"
                    t.error_code = "EXECUTOR_SUBMIT_FAILED"
                    t.error_message = str(e)
                    session.commit()
            raise
        return run_id

    def _wrap(self, tracking_task_id: str, run_id: str, fn, *args, **kwargs):
        try:
            fn(*args, **kwargs)
        except Exception as exc:
            logger.exception(
                "Background workflow entry failed for task_id=%s executor_run_id=%s",
                tracking_task_id,
                run_id,
            )
            with get_sync_session() as session:
                task = session.get(TaskModel, tracking_task_id)
                if task and task.status not in ("SUCCEEDED", "FAILED", "CANCELLED"):
                    task.status = "FAILED"
                    task.error_code = "EXECUTOR_RUNTIME_FAILED"
                    task.error_message = str(exc)
                    session.commit()
        finally:
            self._running.pop(tracking_task_id, None)

    @property
    def active_count(self) -> int:
        return len(self._running)

    def shutdown(self):
        """Stop accepting new tasks. Running tasks continue."""
        self._pool.shutdown(wait=False)
