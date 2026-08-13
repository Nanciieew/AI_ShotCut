#!/usr/bin/env python3
"""Start the Windows development environment.

Usage:
  python scripts/dev/start.py                # Docker infra + native FastAPI
  python scripts/dev/start.py --infra-only   # Docker infra only
  python scripts/dev/start.py --stop          # stop all services
"""

import os
import subprocess
import sys
import time
import urllib.request
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
RUNTIME_DIR = PROJECT_ROOT / "data" / "runtime"
API_PID_FILE = RUNTIME_DIR / "native-api.pid"
API_LOG_FILE = RUNTIME_DIR / "native-api.log"


def _api_port() -> int:
    value = os.getenv("API_PORT")
    env_file = PROJECT_ROOT / ".env"
    if value is None and env_file.exists():
        for line in env_file.read_text(encoding="utf-8-sig").splitlines():
            if line.startswith("API_PORT="):
                value = line.split("=", 1)[1].strip()
                break
    return int(value or "8080")


def _project_python() -> Path:
    candidates = [
        PROJECT_ROOT / ".venv-omnishotcut" / "Scripts" / "python.exe",
        PROJECT_ROOT / ".venv" / "Scripts" / "python.exe",
    ]
    return next((path for path in candidates if path.exists()), Path(sys.executable))


def _api_is_ready(port: int) -> bool:
    try:
        with urllib.request.urlopen(f"http://127.0.0.1:{port}/health/live", timeout=2) as response:
            return response.status == 200
    except Exception:
        return False


def _start_native_api(port: int) -> int:
    if _api_is_ready(port):
        print(f"Native API is already available on port {port}.")
        return 0

    RUNTIME_DIR.mkdir(parents=True, exist_ok=True)
    command = [
        str(_project_python()),
        "-m",
        "uvicorn",
        "apps.api.main:app",
        "--host",
        "127.0.0.1",
        "--port",
        str(port),
    ]
    with API_LOG_FILE.open("a", encoding="utf-8") as log:
        process = subprocess.Popen(
            command,
            cwd=str(PROJECT_ROOT),
            stdin=subprocess.DEVNULL,
            stdout=log,
            stderr=subprocess.STDOUT,
            creationflags=(
                subprocess.CREATE_NEW_PROCESS_GROUP
                | subprocess.DETACHED_PROCESS
                | subprocess.CREATE_BREAKAWAY_FROM_JOB
                if os.name == "nt"
                else 0
            ),
        )
    API_PID_FILE.write_text(str(process.pid), encoding="ascii")
    for _ in range(30):
        if process.poll() is not None:
            print(f"Native API exited early. See {API_LOG_FILE}")
            return process.returncode or 1
        if _api_is_ready(port):
            return 0
        time.sleep(1)
    print(f"Native API did not become ready. See {API_LOG_FILE}")
    return 1


def main() -> int:
    import argparse

    parser = argparse.ArgumentParser(description="Start dev environment.")
    parser.add_argument("--infra-only", action="store_true")
    parser.add_argument("--stop", action="store_true", help="Stop all services")
    args = parser.parse_args()

    if args.stop:
        return subprocess.run(
            [str(_project_python()), "scripts/dev/stop.py"], cwd=str(PROJECT_ROOT)
        ).returncode

    subprocess.run(
        ["docker-compose", "rm", "-s", "-f", "api"],
        cwd=str(PROJECT_ROOT),
        check=False,
    )
    cmd = [
        "docker-compose",
        "up",
        "-d",
        "--build",
        "postgres",
        "migrate",
        "provider",
        "ngrok",
    ]

    result = subprocess.run(cmd, cwd=str(PROJECT_ROOT))
    if result.returncode != 0:
        return result.returncode

    port = _api_port()
    if not args.infra_only:
        result_code = _start_native_api(port)
        if result_code != 0:
            return result_code

    print("\nServices started.")
    if not args.infra_only:
        print(f"  Frontend:    http://localhost:{port}")
        print(f"  API Docs:    http://localhost:{port}/docs")
        print(f"  Health:      http://localhost:{port}/health/live")
        print(f"  API log:     {API_LOG_FILE}")
    print("\nRun 'python scripts/dev/stop.py' to stop.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
