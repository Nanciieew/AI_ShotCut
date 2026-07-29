"""
System information: OS, CPU, memory, disk.

Uses psutil for CPU core count, memory, and disk stats.
If psutil is unavailable, degrades gracefully to os-level fallbacks.
"""

import os
import platform
import sys
from typing import Any, Optional

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_PSUTIL_AVAILABLE = False
try:
    import psutil
    _PSUTIL_AVAILABLE = True
except ImportError:
    pass


def _cpu_model() -> tuple[str | None, str | None]:
    """Return (model_name, warning). model_name is None if undetectable."""
    # Attempt 1: platform.processor() — often empty on Windows
    model = platform.processor()
    if model and model.strip():
        return model.strip(), None

    # Attempt 2: psutil (Linux: /proc/cpuinfo, macOS: sysctl, Win: WMI-like)
    if _PSUTIL_AVAILABLE:
        # cpu_freq is separate; brand_raw is our best bet
        try:
            info = psutil.cpu_freq()
            # Some platforms expose the brand string via frequency reporting
        except Exception:
            pass
        # psutil doesn't reliably expose CPU model name cross-platform
        # Try subprocess as last resort

    # Attempt 3: subprocess
    try:
        if sys.platform == "win32":
            import subprocess
            r = subprocess.run(
                ["wmic", "cpu", "get", "name"],
                capture_output=True, text=True, timeout=10,
            )
            lines = [l.strip() for l in r.stdout.splitlines() if l.strip()]
            if len(lines) >= 2:
                return lines[1], None
        elif sys.platform == "darwin":
            import subprocess
            r = subprocess.run(
                ["sysctl", "-n", "machdep.cpu.brand_string"],
                capture_output=True, text=True, timeout=10,
            )
            if r.returncode == 0 and r.stdout.strip():
                return r.stdout.strip(), None
        elif sys.platform.startswith("linux"):
            import subprocess
            r = subprocess.run(
                ["cat", "/proc/cpuinfo"],
                capture_output=True, text=True, timeout=10,
            )
            for line in r.stdout.splitlines():
                if "model name" in line:
                    return line.split(":", 1)[1].strip(), None
    except Exception:
        pass

    return None, "CPU model name could not be detected cross-platform"


def _psutil_memory() -> tuple[Optional[int], Optional[int]]:
    """Return (total_bytes, available_bytes) via psutil. (None, None) if unavailable."""
    if not _PSUTIL_AVAILABLE:
        return None, None
    try:
        mem = psutil.virtual_memory()
        return mem.total, mem.available
    except Exception:
        return None, None


def _psutil_disk(path: str) -> tuple[Optional[int], Optional[int]]:
    """Return (total_bytes, free_bytes) for the partition containing path."""
    if not _PSUTIL_AVAILABLE:
        return None, None
    try:
        usage = psutil.disk_usage(path)
        return usage.total, usage.free
    except Exception:
        return None, None


def _cpu_count() -> tuple[Optional[int], Optional[int]]:
    """Return (physical_cores, logical_cores)."""
    physical = None
    logical = None
    try:
        logical = os.cpu_count()
    except Exception:
        pass
    if _PSUTIL_AVAILABLE:
        try:
            physical = psutil.cpu_count(logical=False)
        except Exception:
            pass
    return physical, logical


# ---------------------------------------------------------------------------
# Collectors
# ---------------------------------------------------------------------------

def collect_system_info() -> list[dict[str, Any]]:
    """Gather OS, CPU, memory, disk information.

    Returns a list of check dicts.  CPU model failure → WARNING, not FAIL.
    """
    results: list[dict[str, Any]] = []

    # --- OS ---
    results.append({
        "check": "operating_system",
        "status": "PASS",
        "value": platform.system(),
        "detail": platform.platform(aliased=True),
    })

    # --- Architecture ---
    results.append({
        "check": "architecture",
        "status": "PASS",
        "value": platform.machine(),
        "detail": f"Python {sys.version}",
    })

    # --- Python ---
    py_version = f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}"
    results.append({
        "check": "python_version",
        "status": "PASS" if sys.version_info >= (3, 10) else "FAIL",
        "value": py_version,
        "detail": sys.executable,
    })

    # Virtual env detection
    in_venv = (
        hasattr(sys, "real_prefix")
        or (hasattr(sys, "base_prefix") and sys.base_prefix != sys.prefix)
    )
    results.append({
        "check": "python_virtual_env",
        "status": "PASS" if in_venv else "WARNING",
        "value": in_venv,
        "detail": sys.prefix,
    })

    # --- CPU model ---
    model, cpu_warning = _cpu_model()
    results.append({
        "check": "cpu_model",
        "status": "PASS" if model else "WARNING",
        "value": model,
        "detail": cpu_warning,
    })

    # --- CPU cores ---
    phys, logical = _cpu_count()
    results.append({
        "check": "cpu_physical_cores",
        "status": "PASS" if phys is not None else "WARNING",
        "value": phys,
        "detail": None,
    })
    results.append({
        "check": "cpu_logical_cores",
        "status": "PASS" if logical is not None else "WARNING",
        "value": logical,
        "detail": None,
    })

    # --- Memory ---
    total_mem, avail_mem = _psutil_memory()
    if total_mem is not None:
        total_gb = round(total_mem / (1024 ** 3), 1)
        avail_gb = round(avail_mem / (1024 ** 3), 1) if avail_mem else None
        results.append({
            "check": "total_memory_gb",
            "status": "PASS",
            "value": total_gb,
            "detail": f"Available: {avail_gb} GB" if avail_gb else None,
        })
        results.append({
            "check": "available_memory_gb",
            "status": "PASS",
            "value": avail_gb,
            "detail": None,
        })
    else:
        results.append({
            "check": "total_memory_gb",
            "status": "WARNING",
            "value": None,
            "detail": "psutil not available — install with: pip install psutil",
        })
        results.append({
            "check": "available_memory_gb",
            "status": "NOT_RUN",
            "value": None,
            "detail": "Skipped because psutil is missing",
        })

    # --- psutil ---
    results.append({
        "check": "psutil_available",
        "status": "PASS" if _PSUTIL_AVAILABLE else "WARNING",
        "value": _PSUTIL_AVAILABLE,
        "detail": "Required for memory/disk/CPU detail; install with: pip install psutil"
        if not _PSUTIL_AVAILABLE
        else None,
    })

    return results
