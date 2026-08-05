#!/usr/bin/env python3
"""Extract keyframes from normalized video + shots.json — standalone utility.

Usage:
    python scripts/extract_keyframes.py \
        --video data/local_validation/.../normalized.mp4 \
        --shots data/local_validation/.../shots.json \
        --out data/local_validation/.../shot_keyframes/1.0.0 \
        --max-side 672 --quality 85

    # VLM proxy (320×180, ~3min for 2h movie):
    python scripts/extract_keyframes.py ... --vlm-proxy
"""

import argparse, json, sys, time
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from core.media.keyframes import compute_keyframe_targets, extract_keyframes


def main():
    p = argparse.ArgumentParser(description="Extract keyframes from normalized video")
    p.add_argument("--video", required=True, help="Path to normalized.mp4")
    p.add_argument("--shots", required=True, help="Path to shots.json")
    p.add_argument("--out", required=True, help="Output directory for keyframe images")
    p.add_argument("--max-side", type=int, default=672, help="Max long side pixels (default: 672)")
    p.add_argument("--quality", type=int, default=85, help="JPEG quality (default: 85)")
    p.add_argument("--vlm-proxy", action="store_true", help="Extract 320×180 proxy for VLM API (replaces shot_keyframes with shot_keyframes_proxy)")
    p.add_argument("--fps-num", type=int, default=0, help="FPS numerator (auto-detect if 0)")
    p.add_argument("--fps-den", type=int, default=1, help="FPS denominator")
    args = p.parse_args()

    if args.vlm_proxy:
        args.max_side = 320
        args.out = str(Path(args.out).parent.parent / "shot_keyframes_proxy" / "1.0.0")

    video = args.video
    shots_path = args.shots
    out_dir = Path(args.out)

    if not Path(video).exists():
        print(f"ERROR: video not found: {video}"); return 1
    if not Path(shots_path).exists():
        print(f"ERROR: shots not found: {shots_path}"); return 1

    with open(shots_path) as f:
        shots = json.load(f).get("shots", [])
    if not shots:
        print("ERROR: no shots in shots.json"); return 1
    print(f"Shots: {len(shots)}")

    fps_num, fps_den = args.fps_num, args.fps_den
    if fps_num <= 0:
        # Auto-detect from probe or ffprobe
        probe_dir = Path(video).parent
        for probe_name in ["probe_after.json", "probe_before.json"]:
            probe_path = probe_dir / probe_name
            if probe_path.exists():
                with open(probe_path) as f:
                    probe = json.load(f)
                fps_num = probe.get("fps_num", 0)
                fps_den = probe.get("fps_den", 1)
                if fps_num > 0:
                    break
    if fps_num <= 0:
        print("ERROR: cannot determine FPS — use --fps-num/--fps-den"); return 1
    print(f"FPS: {fps_num}/{fps_den}")

    print(f"Computing targets..."); t0 = time.monotonic()
    targets = compute_keyframe_targets(shots, fps_num, fps_den)
    print(f"Targets: {len(targets)} unique frames (from {len(shots) * 3} raw)")

    out_dir.mkdir(parents=True, exist_ok=True)
    result = extract_keyframes(
        video_path=video,
        targets=targets,
        output_dir=out_dir,
        max_long_side=args.max_side,
        quality=args.quality,
    )
    elapsed = time.monotonic() - t0

    print(f"Extracted: {len(result.saved)} images ({result.total_bytes:,} bytes)")
    print(f"Not found: {len(result.not_found)} frames")
    print(f"Time: {elapsed:.1f}s")
    return 0


if __name__ == "__main__":
    sys.exit(main())
