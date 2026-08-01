"""
Celery maintenance tasks — temp file cleanup, failed upload purging, etc.

These tasks run on the 'maintenance' queue (CPU only).
MVP phase: manual invocation. Future: Celery Beat scheduling.
"""

import os
import time
from pathlib import Path

from celery import shared_task

from core.logging.context import clear_task_context, set_task_context

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

DEFAULT_TMP_DIR = os.getenv("STORAGE_ROOT", "./data") + "/tmp"
DEFAULT_MAX_AGE_HOURS = 24
DRY_RUN = os.getenv("MAINTENANCE_DRY_RUN", "false").lower() == "true"


def _get_tmp_dir() -> Path:
    return Path(DEFAULT_TMP_DIR)


# ---------------------------------------------------------------------------
# Tasks
# ---------------------------------------------------------------------------


@shared_task(
    name="maintenance.cleanup_temp_files",
    bind=True,
    max_retries=1,
    queue="maintenance",
)
def cleanup_expired_temp_files(
    self,
    max_age_hours: int | None = None,
    dry_run: bool | None = None,
) -> dict:
    """Delete temp files older than max_age_hours.

    Only cleans files under data/tmp/. Never touches formal Artifacts.
    """
    set_task_context(task_id=self.request.id)

    max_age = max_age_hours or DEFAULT_MAX_AGE_HOURS
    is_dry = dry_run if dry_run is not None else DRY_RUN
    tmp_dir = _get_tmp_dir()

    if not tmp_dir.exists():
        clear_task_context()
        return {"status": "SUCCEEDED", "deleted": 0, "errors": [], "dry_run": is_dry}

    cutoff = time.time() - max_age * 3600
    deleted = []
    errors = []

    for f in tmp_dir.rglob("*"):
        if not f.is_file():
            continue
        try:
            if f.stat().st_mtime < cutoff:
                if not is_dry:
                    f.unlink()
                deleted.append(str(f.relative_to(tmp_dir)))
        except OSError as e:
            errors.append({"file": str(f), "error": str(e)})

    clear_task_context()
    return {
        "status": "SUCCEEDED",
        "deleted": len(deleted),
        "deleted_files": deleted[:100],
        "errors": errors,
        "dry_run": is_dry,
    }


@shared_task(
    name="maintenance.cleanup_failed_uploads",
    bind=True,
    max_retries=1,
    queue="maintenance",
)
def cleanup_failed_uploads(
    self,
    max_age_hours: int | None = None,
    dry_run: bool | None = None,
) -> dict:
    """Remove incomplete / failed upload artifacts.

    Removes files under data/tmp/ that have the .tmp or .partial suffix.
    """
    set_task_context(task_id=self.request.id)

    max_age = max_age_hours or DEFAULT_MAX_AGE_HOURS
    is_dry = dry_run if dry_run is not None else DRY_RUN
    tmp_dir = _get_tmp_dir()

    if not tmp_dir.exists():
        clear_task_context()
        return {"status": "SUCCEEDED", "deleted": 0, "errors": [], "dry_run": is_dry}

    cutoff = time.time() - max_age * 3600
    deleted = []
    errors = []

    for f in tmp_dir.rglob("*"):
        if not f.is_file():
            continue
        if f.suffix not in (".tmp", ".partial"):
            continue
        try:
            if f.stat().st_mtime < cutoff:
                if not is_dry:
                    f.unlink()
                deleted.append(str(f.relative_to(tmp_dir)))
        except OSError as e:
            errors.append({"file": str(f), "error": str(e)})

    clear_task_context()
    return {
        "status": "SUCCEEDED",
        "deleted": len(deleted),
        "deleted_files": deleted[:100],
        "errors": errors,
        "dry_run": is_dry,
    }


@shared_task(
    name="maintenance.cleanup_old_task_results",
    bind=True,
    max_retries=1,
    queue="maintenance",
)
def cleanup_old_task_results(
    self,
    max_age_hours: int | None = None,
    dry_run: bool | None = None,
) -> dict:
    """Purge expired Celery result backend entries.

    The Celery result backend is NOT for long-term artifact storage.
    This task removes entries older than max_age_hours.
    """
    is_dry = dry_run if dry_run is not None else DRY_RUN

    # Celery result expiry is handled by the result_expires config.
    # This is a placeholder for manual cleanup if needed.
    return {
        "status": "SUCCEEDED",
        "deleted": 0,
        "note": (
            "Celery result_expires handles automatic cleanup. "
            "This task is reserved for manual intervention."
        ),
        "dry_run": is_dry,
    }
