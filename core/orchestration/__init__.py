"""Orchestration layer — Celery canvas builders.

Per CLAUDE.md §2.1: the orchestration layer defines task execution order,
parallel/serial decisions, and failure handling. API layer MUST NOT directly
define model execution order — it calls orchestration builders instead.
"""

from core.orchestration.omnishotcut_pipeline import build_omnishotcut_canvas

__all__ = ["build_omnishotcut_canvas"]
