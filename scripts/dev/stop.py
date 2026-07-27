#!/usr/bin/env python3
"""Stop the development environment.

Usage: python scripts/dev/stop.py
"""

import subprocess
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent


def main() -> int:
    print("Stopping services...")
    subprocess.run(
        ["docker-compose", "down", "--remove-orphans"],
        cwd=str(PROJECT_ROOT),
    )
    print("All services stopped.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
