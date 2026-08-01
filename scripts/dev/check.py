#!/usr/bin/env python3
"""Unified dev check: environment + lint + type-check + tests.

Usage: python scripts/dev/check.py [--quick]
"""

import subprocess
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent


def run(cmd: list[str], description: str) -> bool:
    print(f"\n{'=' * 60}")
    print(f"[{description}]")
    print(f"{'=' * 60}")
    result = subprocess.run(cmd, cwd=str(PROJECT_ROOT))
    return result.returncode == 0


def main() -> int:
    import argparse

    parser = argparse.ArgumentParser(description="Run all project checks.")
    parser.add_argument("--quick", action="store_true", help="Skip slow checks (mypy, coverage)")
    args = parser.parse_args()

    checks: list[tuple[list[str], str]] = [
        (["ruff", "check", "."], "Ruff lint"),
        (["ruff", "format", "--check", "."], "Ruff format check"),
    ]

    if not args.quick:
        checks.append((["mypy", "."], "MyPy type check"))

    checks.append((["pytest", "-q"], "Pytest"))

    if not args.quick:
        checks.append(
            (["pytest", "--cov=.", "--cov-report=term-missing", "-q"], "Pytest with coverage")
        )

    failed = 0
    for cmd, desc in checks:
        if not run(cmd, desc):
            failed += 1

    print(f"\n{'=' * 60}")
    print(f"Results: {len(checks) - failed}/{len(checks)} passed")
    if failed:
        print(f"         {failed} failed")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
