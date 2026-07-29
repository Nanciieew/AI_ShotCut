"""
Storage health: disk space, writability for STORAGE_ROOT and MODEL_STORE_ROOT.

Uses psutil for disk usage; falls back to os-level writability test.
"""

import os
import tempfile
from typing import Any, Optional


def _check_directory(path: str) -> dict[str, Any]:
    """Check that a directory exists, is writable, and report disk space.

    Returns {"exists": bool, "writable": bool, "total_gb": int|None, "free_gb": int|None}
    """
    result: dict[str, Any] = {
        "exists": os.path.isdir(path),
        "writable": False,
        "total_gb": None,
        "free_gb": None,
    }

    # Ensure directory
    if not result["exists"]:
        try:
            os.makedirs(path, exist_ok=True)
            result["exists"] = True
        except Exception:
            return result

    # Writable test
    try:
        test_file = os.path.join(path, ".env_check_write_test")
        with open(test_file, "w") as f:
            f.write("ok")
        os.remove(test_file)
        result["writable"] = True
    except Exception:
        pass

    # Disk space via psutil
    try:
        import psutil
        usage = psutil.disk_usage(path)
        result["total_gb"] = round(usage.total / (1024 ** 3), 1)
        result["free_gb"] = round(usage.free / (1024 ** 3), 1)
    except Exception as e:
        result["disk_error"] = str(e)

    return result


def collect_storage_info(
    storage_root: Optional[str] = None,
    model_store_root: Optional[str] = None,
) -> list[dict[str, Any]]:
    """Check STORAGE_ROOT and MODEL_STORE_ROOT directories."""
    results: list[dict[str, Any]] = []

    storage_root = storage_root or os.getenv("STORAGE_ROOT", "./data")
    model_store_root = model_store_root or os.getenv("MODEL_STORE_ROOT", "./model_store")

    for label, path in [("storage_root", storage_root), ("model_store_root", model_store_root)]:
        info = _check_directory(os.path.abspath(path))

        exists_ok = info["exists"] and info["writable"]
        status = "PASS" if exists_ok else "FAIL"

        results.append({
            "check": f"{label}_exists",
            "status": "PASS" if info["exists"] else "FAIL",
            "value": os.path.abspath(path),
            "detail": None if info["exists"] else f"Directory missing: {path}",
        })
        results.append({
            "check": f"{label}_writable",
            "status": "PASS" if info["writable"] else "FAIL",
            "value": info["writable"],
            "detail": None if info["writable"] else f"Cannot write to {path}",
        })
        results.append({
            "check": f"{label}_total_gb",
            "status": "PASS" if info["total_gb"] is not None else "WARNING",
            "value": info["total_gb"],
            "detail": info.get("disk_error") or ("Disk total space" if info["total_gb"] else "psutil.disk_usage failed"),
        })
        results.append({
            "check": f"{label}_free_gb",
            "status": "PASS" if info["free_gb"] is not None else "WARNING",
            "value": info["free_gb"],
            "detail": info.get("disk_error") or ("Disk free space" if info["free_gb"] else "psutil.disk_usage failed"),
        })

    return results
