"""Structured logging configuration and middleware.

Provides:
  - config.py: structlog setup with unified fields
  - context.py: request/task context propagation
  - middleware.py: FastAPI middleware for request_id injection
"""

import logging

import structlog


def configure_logging(
    level: str = "INFO",
    json_output: bool = True,
) -> None:
    """Configure structlog for structured JSON logging.

    All log lines include at minimum:
      timestamp, level, event

    When available (via contextvars):
      task_id, video_id, run_id, model
    """
    timestamper = structlog.processors.TimeStamper(fmt="iso")

    processors = [
        # Merge contextvars-bound variables
        structlog.contextvars.merge_contextvars,
        # Add logger name
        structlog.stdlib.add_logger_name,
        # Add log level
        structlog.stdlib.add_log_level,
        # Filter out log level for cleaner output (level is already in the event dict)
        structlog.stdlib.PositionalArgumentsFormatter(),
        # Add timestamp
        timestamper,
        # Format as JSON or console
        structlog.dev.ConsoleRenderer() if not json_output else structlog.processors.JSONRenderer(),
    ]

    structlog.configure(
        processors=processors,  # type: ignore[arg-type]
        context_class=dict,
        logger_factory=structlog.stdlib.LoggerFactory(),
        wrapper_class=structlog.stdlib.BoundLogger,
        cache_logger_on_first_use=True,
    )

    # Set underlying stdlib logging level
    logging.basicConfig(
        format="%(message)s",
        level=getattr(logging, level.upper(), logging.INFO),
    )


def get_logger(name: str | None = None) -> structlog.stdlib.BoundLogger:
    """Get a structured logger instance."""
    return structlog.get_logger(name or __name__)
