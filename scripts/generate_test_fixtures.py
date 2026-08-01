#!/usr/bin/env python3
"""Generate copyright-free test video fixtures for testing.

Usage: python scripts/generate_test_fixtures.py

Requires FFmpeg on PATH.
"""

import subprocess
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
FIXTURES_DIR = PROJECT_ROOT / "tests" / "fixtures" / "videos"


def generate_test_video(
    filename: str,
    description: str,
    filter_complex: str,
    duration: int = 3,
    fps: int = 24,
    width: int = 640,
    height: int = 480,
) -> bool:
    """Generate a test video using FFmpeg."""
    output_path = FIXTURES_DIR / filename
    if output_path.exists():
        print(f"[SKIP] {filename} already exists")
        return True

    print(f"[GENERATING] {filename} — {description}")
    cmd = [
        "ffmpeg",
        "-y",
        "-f",
        "lavfi",
        "-i",
        filter_complex,
        "-f",
        "lavfi",
        "-i",
        f"sine=frequency=440:duration={duration}",
        "-t",
        str(duration),
        "-r",
        str(fps),
        "-s",
        f"{width}x{height}",
        "-c:v",
        "libx264",
        "-pix_fmt",
        "yuv420p",
        "-c:a",
        "aac",
        "-shortest",
        str(output_path),
    ]
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        print(f"[FAIL] {filename}: {result.stderr[:200]}")
        return False
    print(f"[OK] {filename} ({output_path.stat().st_size} bytes)")
    return True


def main() -> int:
    FIXTURES_DIR.mkdir(parents=True, exist_ok=True)

    videos = [
        (
            "no_cut.mp4",
            "Static color — no shot boundary",
            "color=c=blue:s=640x480:d=3",
        ),
        (
            "hard_cut.mp4",
            "Single hard cut at midpoint",
            "color=c=red:s=640x480:d=1.5,color=c=green:s=640x480:d=1.5",
        ),
        (
            "multiple_cuts.mp4",
            "Three hard cuts",
            "color=c=red:s=640x480:d=1,color=c=green:s=640x480:d=1,color=c=blue:s=640x480:d=1,color=c=yellow:s=640x480:d=1",
        ),
    ]

    all_ok = True
    for filename, desc, vfilter in videos:
        if not generate_test_video(filename, desc, vfilter):
            all_ok = False

    if all_ok:
        print("\nAll test fixtures generated.")
    else:
        print("\nSome fixtures failed. Is FFmpeg installed?")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
