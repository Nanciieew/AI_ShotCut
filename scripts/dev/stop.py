#!/usr/bin/env python3
"""Stop the development environment.

Usage: python scripts/dev/stop.py
"""

import subprocess
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
API_PID_FILE = PROJECT_ROOT / "data" / "runtime" / "native-api.pid"


def _stop_native_api() -> None:
    if not API_PID_FILE.exists():
        return
    try:
        pid = int(API_PID_FILE.read_text(encoding="ascii").strip())
        if sys.platform == "win32":
            probe = subprocess.run(
                [
                    "powershell",
                    "-NoProfile",
                    "-Command",
                    f"(Get-CimInstance Win32_Process -Filter 'ProcessId={pid}').CommandLine",
                ],
                capture_output=True,
                text=True,
                check=False,
            )
            if "uvicorn" in probe.stdout and "apps.api.main:app" in probe.stdout:
                subprocess.run(["taskkill", "/PID", str(pid), "/T", "/F"], check=False)
        else:
            subprocess.run(["kill", str(pid)], check=False)
    finally:
        API_PID_FILE.unlink(missing_ok=True)


def main() -> int:
    print("Stopping services...")
    _stop_native_api()
    subprocess.run(
        ["docker-compose", "--profile", "container-api", "down", "--remove-orphans"],
        cwd=str(PROJECT_ROOT),
    )
    print("All services stopped.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
