"""
Celery application factory.

Loads configuration from configs/celery.yaml and environment variables.
All long-running tasks (FFmpeg, model inference, feature extraction)
MUST be executed as Celery tasks, never synchronously in an HTTP request.
"""

import os
from celery import Celery
from celery.signals import worker_ready, worker_shutdown

_app: Celery | None = None


def create_celery_app() -> Celery:
    """Create and configure the Celery application instance."""
    global _app

    broker_url = os.getenv("CELERY_BROKER_URL", "redis://localhost:6379/0")
    result_backend = os.getenv("CELERY_RESULT_BACKEND", "redis://localhost:6379/1")

    app = Celery(
        "movie_analysis",
        broker=broker_url,
        backend=result_backend,
        include=[
            "workers.tasks.video_tasks",
            "workers.tasks.shot_tasks",
            "workers.tasks.subtitle_tasks",
            "workers.tasks.feature_tasks",
            "workers.tasks.scene_tasks",
            "workers.tasks.final_tasks",
        ],
    )

    # --- Core settings (from configs/celery.yaml defaults) ---
    app.conf.update(
        task_serializer="json",
        result_serializer="json",
        accept_content=["json"],
        timezone="Asia/Shanghai",
        enable_utc=True,
        task_track_started=True,
        task_acks_late=True,
        task_reject_on_worker_lost=True,
        worker_prefetch_multiplier=1,
        broker_connection_retry_on_startup=True,
        task_soft_time_limit=3600,   # 1 hour soft limit
        task_time_limit=7200,        # 2 hour hard limit
        result_expires=3600,         # purge results after 1 hour
        worker_concurrency=1,
        worker_max_tasks_per_child=50,
    )

    _app = app
    return app


def get_celery_app() -> Celery:
    """Return the singleton Celery app instance (lazy initialization)."""
    global _app
    if _app is None:
        _app = create_celery_app()
    return _app


# Module-level instance for Celery's -A flag
app = get_celery_app()
