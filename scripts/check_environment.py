#!/usr/bin/env python3
"""
Project-level environment report — Movie Analysis Platform.

Checks OS, CPU, memory, disk, executables, PyTorch, CUDA, storage.

Usage:
    python scripts/check_environment.py
    python scripts/check_environment.py --json
    python scripts/check_environment.py --output report.json
"""

import argparse
import os
import sys
from pathlib import Path

# Ensure project root is on sys.path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from core.environment import EnvironmentReport


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Project-level environment report — Movie Analysis Platform"
    )
    parser.add_argument("--json", action="store_true", help="Output JSON to stdout")
    parser.add_argument("--output", type=str, default=None, help="Write report to file")
    parser.add_argument("--text", action="store_true", help="Output human-readable text (default)")
    args = parser.parse_args()

    # ------------------------------------------------------------------
    # Collect
    # ------------------------------------------------------------------
    report = EnvironmentReport()

    report.add_system_info()
    report.add_executable_info()
    report.add_pytorch_info()
    report.add_storage_info(
        storage_root=os.getenv("STORAGE_ROOT", "./data"),
        model_store_root=os.getenv("MODEL_STORE_ROOT", "./model_store"),
    )

    report.finalize()

    # ------------------------------------------------------------------
    # Output
    # ------------------------------------------------------------------
    if args.json:
        output = report.to_json()
    else:
        output = report.to_text()

    if args.output:
        with open(args.output, "w", encoding="utf-8") as f:
            f.write(output)
        print(f"Report written to {args.output}")
    else:
        print(output)

    # Exit code: 0 for READY / READY_WITH_WARNINGS, 1 for BLOCKED
    if report.overall and report.overall.value == "BLOCKED":
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
