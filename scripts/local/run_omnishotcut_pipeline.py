#!/usr/bin/env python3
"""Local OmniShotCut pipeline runner.

Runs the complete pipeline without Docker/Celery/Redis/PostgreSQL.
Calls the same Pipeline Service that future Celery tasks will use.

Usage:
  python scripts/local/run_omnishotcut_pipeline.py \
    --video tests/fixtures/videos/omnishotcut/Hard_Cut_1.mp4 \
    --output-root data/local_validation \
    --mode clean_shot
"""

import argparse
import sys
import time
from pathlib import Path

# Ensure project root is on sys.path
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT))


def main() -> int:
    parser = argparse.ArgumentParser(description="Run OmniShotCut pipeline locally")
    parser.add_argument(
        "--video",
        required=True,
        help="Path to source video file (e.g. tests/fixtures/videos/omnishotcut/Hard_Cut_1.mp4)",
    )
    parser.add_argument(
        "--output-root",
        default="data/local_validation",
        help="Root directory for output artifacts (default: data/local_validation)",
    )
    parser.add_argument(
        "--mode",
        default="clean_shot",
        choices=["clean_shot", "all"],
        help="OmniShotCut inference mode (default: clean_shot)",
    )
    parser.add_argument(
        "--video-id",
        default=None,
        help="Custom video_id (default: derived from filename)",
    )
    parser.add_argument(
        "--extract-keyframes",
        action="store_true",
        default=False,
        help="Extract 25%%, 50%%, 75%% keyframes per shot after shot detection",
    )
    args = parser.parse_args()

    # --- Locate video ---
    video_path = Path(args.video)
    if not video_path.is_absolute():
        # Try relative to project root
        video_path = PROJECT_ROOT / args.video

    if not video_path.exists():
        print(f"[ERROR] Video not found: {video_path}")
        print(f"        Tried: {args.video}")
        print(f"        Tried: {video_path}")
        return 1

    output_root = Path(args.output_root)
    if not output_root.is_absolute():
        output_root = PROJECT_ROOT / args.output_root

    video_id = args.video_id or video_path.stem

    # --- Run pipeline ---
    from pipelines.services.omnishotcut_pipeline import run_omnishotcut_pipeline

    print("=" * 60)
    print("OmniShotCut Local Pipeline")
    print("=" * 60)
    print(f"  Video:       {video_path}")
    print(f"  Video ID:    {video_id}")
    print(f"  Output:      {output_root}")
    print(f"  Mode:        {args.mode}")
    print(f"  Size:        {video_path.stat().st_size / 1024 / 1024:.1f} MB")
    print()

    t0 = time.monotonic()
    result = run_omnishotcut_pipeline(
        video_id=video_id,
        source_video_path=video_path,
        output_root=output_root,
        mode=args.mode,
        extract_keyframes=args.extract_keyframes,
    )
    wall_s = time.monotonic() - t0

    # --- Report ---
    print(f"\n{'=' * 60}")
    print(f"RESULT: {result.status}")
    print(f"{'=' * 60}")
    print(f"  Wall time:        {wall_s:.1f}s")
    print(f"  Pipeline time:    {result.runtime_ms / 1000:.1f}s")
    print()

    if result.probe_before:
        p = result.probe_before
        print("  [Probe Before]")
        print(f"    Codec:         {p.get('video_codec')}")
        print(f"    Resolution:    {p.get('width')}x{p.get('height')}")
        print(
            f"    FPS:           {p.get('fps_num')}/{p.get('fps_den')} = {p.get('fps_num', 0) / max(p.get('fps_den', 1), 1):.3f}"
        )
        print(f"    Frame mode:    {p.get('frame_rate_mode')}")
        print(f"    Duration:      {p.get('duration_ms')}ms")
        print(f"    Has audio:     {p.get('has_audio')}")
        print()

    if result.probe_after:
        p = result.probe_after
        print("  [Probe After]")
        print(f"    Codec:         {p.get('video_codec')}")
        print(f"    Pixel fmt:     {p.get('pixel_format')}")
        print(f"    FPS:           {p.get('fps_num')}/{p.get('fps_den')}")
        print(f"    Duration:      {p.get('duration_ms')}ms")
        print(f"    Container:     {p.get('container_format')}")
        print()

    print("  [Normalization]")
    print(f"    FFmpeg:        {result.ffmpeg_version}")
    print(f"    Input SHA256:  {result.input_sha256}")
    print(f"    Output SHA256: {result.normalized_sha256}")
    print(f"    Artifact ID:   {result.normalized_artifact_id}")
    print(f"    Artifact URI:  {result.normalized_artifact_uri}")
    print()

    print("  [OmniShotCut]")
    print(f"    Shot count:    {result.shot_count}")
    print(f"    Artifact ID:   {result.shots_artifact_id}")
    print(f"    Artifact URI:  {result.shots_artifact_uri}")
    print(f"    SHA256:        {result.shots_sha256}")
    print()

    if result.keyframes_artifact_uri:
        print(f"  [Keyframes]")
        print(f"    Artifact URI:  {result.keyframes_artifact_uri}")
        print(f"    Image count:   {result.keyframe_image_count or 0}")
        print()

    if result.warnings:
        print("  [Warnings]")
        for w in result.warnings:
            print(f"    - {w}")
        print()

    if result.status == "FAILED":
        print(f"  [ERROR] {result.error_code}: {result.error_message}")
        print()
        return 1

    return 0


if __name__ == "__main__":
    sys.exit(main())
