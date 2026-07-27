"""
Celery signal handlers for structured logging and lifecycle management.

Each signal handler emits a structured log line that includes at minimum:
  - timestamp
  - level
  - task_id (when available)
  - event name
"""

import logging
from celery import signals
from celery.utils.log import get_task_logger

logger = get_task_logger(__name__)


@signals.task_prerun.connect
def on_task_prerun(sender=None, task_id=None, task=None, args=None, kwargs=None, **extra):
    logger.info(
        "task_started",
        extra={
            "task_id": task_id,
            "task_name": task.name if task else "unknown",
            "event": "task_started",
        },
    )


@signals.task_success.connect
def on_task_success(sender=None, result=None, **extra):
    task_id = sender.request.id if sender and hasattr(sender, "request") else None
    logger.info(
        "task_succeeded",
        extra={
            "task_id": task_id,
            "task_name": sender.name if sender else "unknown",
            "event": "task_succeeded",
        },
    )


@signals.task_failure.connect
def on_task_failure(sender=None, task_id=None, exception=None, traceback=None, **extra):
    logger.error(
        "task_failed",
        extra={
            "task_id": task_id,
            "task_name": sender.name if sender else "unknown",
            "event": "task_failed",
            "error": str(exception),
        },
    )


@signals.worker_ready.connect
def on_worker_ready(sender=None, **extra):
    logger.info("worker_ready", extra={"event": "worker_ready"})


@signals.worker_shutdown.connect
def on_worker_shutdown(sender=None, **extra):
    logger.info("worker_shutdown", extra={"event": "worker_shutdown"})
