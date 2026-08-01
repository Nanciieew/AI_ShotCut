"""
Executable detection: FFmpeg, FFprobe, Docker, nvidia-smi.

Each check returns {"check": str, "status": str, "value": ..., "detail": ...}
"""

import shutil
import subprocess
import sys
from typing import Any


def _which_version(cmd: str, version_flag: str = "-version") -> tuple[str | None, str | None, str]:
    """Locate executable and extract its first version line.

    Returns (path, version_line, status).
    """
    path = shutil.which(cmd)
    if path is None:
        return None, None, "NOT_INSTALLED"
    try:
        r = subprocess.run(
            [cmd, version_flag],
            capture_output=True,
            text=True,
            timeout=15,
        )
        # Some tools write version to stderr (ffmpeg, ffprobe)
        output = r.stdout + r.stderr
        first_line = output.strip().split("\n")[0] if output.strip() else "unknown"
        return path, first_line, "PASS"
    except Exception:
        return path, None, "WARNING"


def collect_executable_info(
    storage_root: str | None = None,
) -> list[dict[str, Any]]:
    """Check all required external executables."""
    results: list[dict[str, Any]] = []

    # --- FFmpeg ---
    path, ver, status = _which_version("ffmpeg")
    results.append(
        {
            "check": "ffmpeg",
            "status": status,
            "value": path,
            "detail": ver,
        }
    )

    # --- FFprobe ---
    path, ver, status = _which_version("ffprobe")
    results.append(
        {
            "check": "ffprobe",
            "status": status,
            "value": path,
            "detail": ver,
        }
    )

    # --- Docker ---
    path, ver, status = _which_version("docker", version_flag="--version")
    results.append(
        {
            "check": "docker",
            "status": status,
            "value": path,
            "detail": ver,
        }
    )

    # --- nvidia-smi ---
    nv_path = shutil.which("nvidia-smi") if sys.platform != "darwin" else None
    if nv_path:
        try:
            r = subprocess.run(
                ["nvidia-smi", "--query-gpu=name,driver_version", "--format=csv,noheader"],
                capture_output=True,
                text=True,
                timeout=15,
            )
            detail = r.stdout.strip() if r.returncode == 0 else None
        except Exception:
            detail = None
        results.append(
            {
                "check": "nvidia_smi",
                "status": "PASS" if detail else "WARNING",
                "value": nv_path,
                "detail": detail,
            }
        )
    else:
        results.append(
            {
                "check": "nvidia_smi",
                "status": "NOT_INSTALLED",
                "value": None,
                "detail": "nvidia-smi not on PATH",
            }
        )

    # --- Redis / PostgreSQL config presence (no secrets) ---
    import os

    redis_url = os.getenv("REDIS_URL") or os.getenv("CELERY_BROKER_URL")
    db_url = os.getenv("DATABASE_URL")

    results.append(
        {
            "check": "redis_configured",
            "status": "PASS" if redis_url else "WARNING",
            "value": bool(redis_url),
            "detail": "REDIS_URL or CELERY_BROKER_URL is set"
            if redis_url
            else "No Redis configuration found",
        }
    )

    # Only report DB type, never the full URL
    db_type = "unknown"
    if db_url:
        if "sqlite" in db_url:
            db_type = "sqlite"
        elif "postgres" in db_url:
            db_type = "postgresql"
    results.append(
        {
            "check": "database_configured",
            "status": "PASS" if db_url else "WARNING",
            "value": db_type,
            "detail": "DATABASE_URL is set"
            if db_url
            else "No DATABASE_URL — will default to SQLite",
        }
    )

    return results
