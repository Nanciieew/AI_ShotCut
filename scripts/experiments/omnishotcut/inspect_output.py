#!/usr/bin/env python3
"""Inspect OmniShotCut raw output files.

Usage:
  python scripts/experiments/omnishotcut/inspect_output.py
  python scripts/experiments/omnishotcut/inspect_output.py --file Hard_Cut_1_raw.json
"""

import argparse
import json
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent.parent
OUTPUT_DIR = PROJECT_ROOT / "tests" / "fixtures" / "raw_outputs" / "omnishotcut"


def inspect_file(filepath: Path) -> None:
    raw = json.loads(filepath.read_text(encoding="utf-8"))
    print(f"\n{'=' * 60}")
    print(f"File: {filepath.name}")
    print(f"{'=' * 60}")
    print(f"  Video:        {raw.get('video')}")
    print(f"  FPS:          {raw.get('fps_num')}/{raw.get('fps_den')} = {raw.get('fps')}")
    print(f"  Frames:       {raw.get('frame_count')}")
    print(f"  Duration:     {raw.get('duration_s')}s")
    print(f"  Mode:         {raw.get('mode')}")
    print(f"  Runtime:      {raw.get('runtime_s')}s")
    print(f"  Shot count:   {raw.get('shot_count')}")
    print(f"  Error:        {raw.get('error')}")
    ranges = raw.get("raw_ranges")
    if ranges:
        print("\n  Raw ranges (first 5):")
        for r in ranges[:5]:
            print(f"    [{r[0]:>6}, {r[1]:>6}] inclusive, len={r[1] - r[0] + 1}f")
        fps = raw["fps_num"] / raw["fps_den"]
        s0, e0 = ranges[0]
        print(
            f"\n  First→ms: [{s0},{e0}] → [{round(s0 * 1000 / fps)}, {round((e0 + 1) * 1000 / fps)})"
        )


def main() -> int:
    parser = argparse.ArgumentParser(description="Inspect OmniShotCut raw outputs")
    parser.add_argument("--file", help="Specific file to inspect")
    args = parser.parse_args()
    if not OUTPUT_DIR.exists():
        print("No outputs yet. Run run_raw_inference.py first.")
        return 0
    if args.file:
        fp = OUTPUT_DIR / args.file
        if not fp.exists():
            print(f"Not found: {fp}")
            return 1
        inspect_file(fp)
    else:
        files = sorted(OUTPUT_DIR.glob("*_raw.json"))
        if not files:
            print(f"No raw output files in {OUTPUT_DIR}")
            return 0
        for fp in files:
            inspect_file(fp)
    return 0


if __name__ == "__main__":
    sys.exit(main())
