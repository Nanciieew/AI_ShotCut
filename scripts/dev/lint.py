#!/usr/bin/env python3
"""Run lint and format checks.

Usage: python scripts/dev/lint.py [--fix]
"""

import subprocess
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent


def main() -> int:
    import argparse

    parser = argparse.ArgumentParser(description="Run lint checks.")
    parser.add_argument("--fix", action="store_true", help="Auto-fix issues")
    args = parser.parse_args()

    if args.fix:
        print("Running ruff --fix ...")
        subprocess.run(["ruff", "check", "--fix", "."], cwd=str(PROJECT_ROOT))
        subprocess.run(["ruff", "format", "."], cwd=str(PROJECT_ROOT))
    else:
        print("Running ruff check ...")
        subprocess.run(["ruff", "check", "."], cwd=str(PROJECT_ROOT))
        subprocess.run(["ruff", "format", "--check", "."], cwd=str(PROJECT_ROOT))

    return 0


if __name__ == "__main__":
    sys.exit(main())
