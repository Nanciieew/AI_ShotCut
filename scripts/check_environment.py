#!/usr/bin/env python3
"""
Environment check script.

Verifies that all required system dependencies and Python packages
are available before starting development.

Usage:
    python scripts/check_environment.py
"""

import shutil
import subprocess
import sys


def check_python_version() -> bool:
    """Require Python 3.10 or later."""
    major, minor = sys.version_info[:2]
    ok = (major, minor) >= (3, 10)
    if ok:
        print(f"[OK] Python {major}.{minor}")
    else:
        print(f"[FAIL] Python {major}.{minor} — need 3.10+")
    return ok


def check_ffmpeg() -> bool:
    """Check that FFmpeg is on PATH."""
    found = shutil.which("ffmpeg") is not None
    if found:
        print(f"[OK] FFmpeg found at {shutil.which('ffmpeg')}")
    else:
        print("[FAIL] FFmpeg not found on PATH")
    return found


def check_redis() -> bool:
    """Check that redis-cli can reach the server."""
    try:
        result = subprocess.run(
            ["redis-cli", "ping"],
            capture_output=True,
            text=True,
            timeout=5,
        )
        ok = "PONG" in result.stdout
        if ok:
            print("[OK] Redis responding to PING")
        else:
            print(f"[FAIL] Redis responded: {result.stdout.strip()}")
        return ok
    except FileNotFoundError:
        print("[WARN] redis-cli not found — install Redis or skip this check")
        return False
    except Exception as e:
        print(f"[WARN] Redis check failed: {e}")
        return False


def check_packages() -> bool:
    """Check that key Python packages are importable."""
    packages = [
        "fastapi",
        "uvicorn",
        "celery",
        "redis",
        "sqlalchemy",
        "pydantic",
        "yaml",
    ]
    all_ok = True
    for pkg in packages:
        try:
            __import__(pkg)
            print(f"[OK] {pkg}")
        except ImportError:
            print(f"[FAIL] {pkg} — run: pip install -r requirements.txt")
            all_ok = False
    return all_ok


def main() -> int:
    print("=" * 50)
    print("Environment Check — Movie Analysis Platform")
    print("=" * 50)

    checks = [
        ("Python 3.10+", check_python_version),
        ("FFmpeg", check_ffmpeg),
        ("Redis", check_redis),
        ("Python packages", check_packages),
    ]

    results = {}
    for name, fn in checks:
        results[name] = fn()
        print()

    passed = sum(results.values())
    total = len(results)
    print(f"Result: {passed}/{total} checks passed")

    return 0 if passed == total else 1


if __name__ == "__main__":
    sys.exit(main())
