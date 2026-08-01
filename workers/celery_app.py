"""
Celery application factory.

Loads configuration from environment variables.
All long-running tasks (FFmpeg, model inference, feature extraction)
MUST be executed as Celery tasks, never synchronously in an HTTP request.
"""

import os

from celery import Celery

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
            "workers.tasks.maintenance_tasks",
        ],
    )

    # --- Core settings ---
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
        task_soft_time_limit=3600,
        task_time_limit=7200,
        result_expires=3600,
        worker_concurrency=1,
        worker_max_tasks_per_child=50,
    )

    # --- Task routing: dedicated queues ---
    app.conf.task_routes = {
        "workers.tasks.video_tasks.*": {"queue": "video"},
        "workers.tasks.shot_tasks.*": {"queue": "shot"},
        "workers.tasks.subtitle_tasks.*": {"queue": "subtitle"},
        "workers.tasks.feature_tasks.*": {"queue": "feature"},
        "workers.tasks.scene_tasks.*": {"queue": "scene"},
        "workers.tasks.final_tasks.*": {"queue": "final"},
        "workers.tasks.maintenance_tasks.*": {"queue": "maintenance"},
    }

    # --- Task default queue ---
    app.conf.task_default_queue = "video"
    app.conf.task_default_routing_key = "video"

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
