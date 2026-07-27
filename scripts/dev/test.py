#!/usr/bin/env python3
"""Run tests with optional coverage.

Usage: python scripts/dev/test.py [--cov] [--unit] [--integration]
"""

import subprocess
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent


def main() -> int:
    import argparse

    parser = argparse.ArgumentParser(description="Run tests.")
    parser.add_argument("--cov", action="store_true", help="Include coverage report")
    parser.add_argument("--unit", action="store_true", help="Only unit tests")
    parser.add_argument("--integration", action="store_true", help="Only integration tests")
    args = parser.parse_args()

    cmd = ["pytest", "-q"]

    if args.unit:
        cmd.append("tests/unit/")
    elif args.integration:
        cmd.append("tests/integration/")

    if args.cov:
        cmd.extend(["--cov=.", "--cov-report=term-missing"])

    result = subprocess.run(cmd, cwd=str(PROJECT_ROOT))
    return result.returncode


if __name__ == "__main__":
    sys.exit(main())
