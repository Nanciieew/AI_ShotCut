"""Logging context — inject task/video/run IDs into log lines.

Usage:
    from core.logging.context import set_task_context, clear_task_context

    set_task_context(task_id="task_001", video_id="video_001", run_id="run_001")
    logger.info("inference_started")  # automatically includes the ids
"""

import structlog


def set_task_context(
    *,
    task_id: str | None = None,
    video_id: str | None = None,
    run_id: str | None = None,
    model: str | None = None,
    request_id: str | None = None,
) -> None:
    """Bind task-level identifiers to the current context.

    These values automatically appear in every log line emitted
    within the same context (thread/async task).
    """
    bindings: dict[str, str] = {}
    if task_id:
        bindings["task_id"] = task_id
    if video_id:
        bindings["video_id"] = video_id
    if run_id:
        bindings["run_id"] = run_id
    if model:
        bindings["model"] = model
    if request_id:
        bindings["request_id"] = request_id
    if bindings:
        structlog.contextvars.bind_contextvars(**bindings)


def clear_task_context() -> None:
    """Clear all bound context variables."""
    structlog.contextvars.clear_contextvars()
