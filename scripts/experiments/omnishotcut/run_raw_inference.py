#!/usr/bin/env python3
"""
OmniShotCut raw inference runner — SPIKE experiment script.

Runs the model against test videos and saves raw output + metadata
to tests/fixtures/raw_outputs/omnishotcut/.

Usage:
  python scripts/experiments/omnishotcut/run_raw_inference.py
  python scripts/experiments/omnishotcut/run_raw_inference.py --video Hard_Cut_1.mp4
"""

import argparse
import json
import os
import subprocess
import sys
import time
from pathlib import Path

# Path resolver relative to project root
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent.parent
VIDEOS_DIR = PROJECT_ROOT / "tests" / "fixtures" / "videos" / "omnishotcut"
OUTPUT_DIR = PROJECT_ROOT / "tests" / "fixtures" / "raw_outputs" / "omnishotcut"


def get_fps(video_path: str) -> tuple[int, int]:
    """Get FPS as num/den via ffprobe."""
    try:
        r = subprocess.run(
            [
                "ffprobe", "-v", "quiet",
                "-select_streams", "v:0",
                "-show_entries", "stream=r_frame_rate",
                "-of", "json", video_path,
            ],
            capture_output=True, text=True, timeout=15,
        )
        info = json.loads(r.stdout)
        fps_str = info["streams"][0]["r_frame_rate"]
        num, den = fps_str.split("/")
        return int(num), int(den)
    except Exception:
        return 24000, 1001


def get_frame_count(video_path: str) -> int:
    """Get total frame count via ffprobe."""
    try:
        r = subprocess.run(
            [
                "ffprobe", "-v", "quiet",
                "-select_streams", "v:0",
                "-count_frames", "-show_entries",
                "stream=nb_read_frames",
                "-of", "json", video_path,
            ],
            capture_output=True, text=True, timeout=15,
        )
        info = json.loads(r.stdout)
        return int(info["streams"][0]["nb_read_frames"])
    except Exception:
        return -1


def main() -> int:
    parser = argparse.ArgumentParser(description="OmniShotCut raw inference runner")
    parser.add_argument("--video", help="Specific video filename (default: all .mp4 in fixtures)")
    args = parser.parse_args()

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    # Collect videos
    if args.video:
        videos = [VIDEOS_DIR / args.video]
    else:
        videos = sorted(VIDEOS_DIR.glob("*.mp4"))

    if not videos or (len(videos) == 1 and not videos[0].exists()):
        print(f"[SKIP] No test videos found in {VIDEOS_DIR}")
        print(f"       Place .mp4 files there and re-run.")
        return 0

    # Load model once
    print("Loading OmniShotCut ...")
    import omnishotcut

    weight_path = os.path.join(
        os.getenv("MODEL_STORE_ROOT", str(PROJECT_ROOT / "model_store")),
        "omnishotcut/1.0.0/OmniShotCut_ckpt.pth",
    )
    model = omnishotcut.load(weight_path)

    results = []

    for vp in videos:
        vpath = str(vp)
        vname = vp.name
        print(f"\n{'='*50}")
        print(f"Video: {vname} ({vp.stat().st_size / 1024 / 1024:.1f} MB)")

        fps_num, fps_den = get_fps(vpath)
        frame_count = get_frame_count(vpath)
        fps_val = fps_num / fps_den
        duration_s = frame_count / fps_val if frame_count > 0 else -1

        print(f"  FPS: {fps_num}/{fps_den} = {fps_val:.3f}")
        print(f"  Frames: {frame_count}, Duration: {duration_s:.1f}s")

        t0 = time.monotonic()
        error = None
        raw_ranges = None
        try:
            raw_ranges = model.inference(vpath, mode="clean_shot")
            runtime_s = time.monotonic() - t0
            print(f"  Runtime: {runtime_s:.1f}s, Shots: {len(raw_ranges)}")
        except Exception as e:
            runtime_s = time.monotonic() - t0
            error = str(e)
            print(f"  [FAIL] {error}")

        # Save raw output
        safe_name = vname.rsplit(".", 1)[0]
        output_file = OUTPUT_DIR / f"{safe_name}_raw.json"

        entry = {
            "video": vname,
            "fps_num": fps_num,
            "fps_den": fps_den,
            "fps": round(fps_val, 4),
            "frame_count": frame_count,
            "duration_s": round(duration_s, 2) if duration_s >= 0 else None,
            "mode": "clean_shot",
            "runtime_s": round(runtime_s, 2),
            "shot_count": len(raw_ranges) if raw_ranges else 0,
            "error": error,
            "raw_ranges": raw_ranges,
        }

        with open(output_file, "w", encoding="utf-8") as f:
            json.dump(entry, f, indent=2, ensure_ascii=False, default=str)
        print(f"  Saved: {output_file}")

        results.append(entry)

    # Summary
    print(f"\n{'='*50}")
    print("SUMMARY")
    print(f"{'='*50}")
    for r in results:
        status = "OK" if r["error"] is None else "FAIL"
        print(f"  {r['video']:<30} {status}  {r['shot_count']:>4} shots  {r['runtime_s']:>6.1f}s")

    # Save summary
    summary_file = OUTPUT_DIR / "_summary.json"
    with open(summary_file, "w", encoding="utf-8") as f:
        json.dump(results, f, indent=2, ensure_ascii=False, default=str)
    print(f"\nSummary: {summary_file}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
