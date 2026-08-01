#!/usr/bin/env python3
"""Start the development environment.

Usage:
  python scripts/dev/start.py                # start all services
  python scripts/dev/start.py --api-only     # only API + Redis + Postgres
  python scripts/dev/start.py --stop          # stop all services
"""

import subprocess
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent


def main() -> int:
    import argparse

    parser = argparse.ArgumentParser(description="Start dev environment.")
    parser.add_argument("--api-only", action="store_true")
    parser.add_argument("--stop", action="store_true", help="Stop all services")
    args = parser.parse_args()

    if args.stop:
        subprocess.run(["docker-compose", "down"], cwd=str(PROJECT_ROOT))
        return 0

    cmd = ["docker-compose", "up", "-d"]
    if args.api_only:
        cmd.extend(["api", "redis", "postgres"])
    else:
        cmd.append("--build")

    result = subprocess.run(cmd, cwd=str(PROJECT_ROOT))
    if result.returncode != 0:
        return result.returncode

    print("\nServices starting...")
    print("  API:         http://localhost:8000")
    print("  API Docs:    http://localhost:8000/docs")
    print("  Health:      http://localhost:8000/health")
    print("\nRun 'python scripts/dev/stop.py' to stop.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
