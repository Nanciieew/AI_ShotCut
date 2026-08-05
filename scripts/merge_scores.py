"""Merge location+character+plot scores → final scenes.

Usage:
    python merge_scores.py                              # default weighted 35/35/30
    python merge_scores.py --mode location_only           # only location
    python merge_scores.py --mode character_only          # only character
    python merge_scores.py --mode plot_only               # only plot
    python merge_scores.py --mode custom --L 5 --C 3 --P 2  # custom 5:3:2
"""

import argparse
import json


def compute_weights(mode: str, L: int, C: int, P: int) -> tuple[float, float, float]:
    if mode == "location_only":
        return (1.0, 0.0, 0.0)
    elif mode == "character_only":
        return (0.0, 1.0, 0.0)
    elif mode == "plot_only":
        return (0.0, 0.0, 1.0)
    elif mode == "custom":
        total = L + C + P
        return (L / total, C / total, P / total) if total > 0 else (0.35, 0.35, 0.30)
    else:
        return (0.35, 0.35, 0.30)


def main():
    p = argparse.ArgumentParser(description="Merge scores → final scenes")
    p.add_argument(
        "--mode",
        default="weighted",
        choices=["weighted", "location_only", "character_only", "plot_only", "custom"],
    )
    p.add_argument("--L", type=int, default=35, help="Location weight 1-10 (custom mode)")
    p.add_argument("--C", type=int, default=35, help="Character weight 1-10 (custom mode)")
    p.add_argument("--P", type=int, default=30, help="Plot weight 1-10 (custom mode)")
    p.add_argument(
        "--intensity",
        default="medium",
        choices=["high", "medium", "low"],
        help="high=6%%, medium=4%%, low=1%% of shots as target scene count",
    )
    p.add_argument(
        "--min-distance-s", type=int, default=12, help="Minimum seconds between selected boundaries"
    )
    p.add_argument(
        "--shots",
        default="data/local_validation/projects/local_validation/videos/SceneSeg_Test1/artifacts/omnishotcut/0.1.0/shots.json",
    )
    p.add_argument("--vlm", default="data/sceneseg_test1_qwen_vlm_scores.json")
    p.add_argument("--plot", default="data/sceneseg_test1_deepseek_plot_v2.json")
    p.add_argument("--out", default="data/sceneseg_test1_final_result.json")
    args = p.parse_args()

    W = compute_weights(args.mode, args.L, args.C, args.P)
    INTENSITY_RATIOS = {"high": 0.06, "medium": 0.04, "low": 0.01}
    MIN_DISTANCE_MS = args.min_distance_s * 1000

    # Load
    with open(args.shots) as f:
        shots = json.load(f)["shots"]
    vlm_scores = {}
    try:
        with open(args.vlm, encoding="utf-8") as f:
            vlm_scores = {s["shot_id"]: s for s in json.load(f).get("scores", [])}
    except FileNotFoundError:
        print("WARNING: VLM scores not found")
    plot_by_shot = {}
    try:
        with open(args.plot, encoding="utf-8") as f:
            for pp in json.load(f).get("plot_scores", []):
                plot_by_shot[pp["shot_id"]] = pp
    except FileNotFoundError:
        print("WARNING: Plot scores not found")

    # Score every boundary
    merged = []
    for i, shot in enumerate(shots[:-1]):
        sid = shot["shot_id"]
        q = vlm_scores.get(sid, {})
        loc = q.get("location_change", 0)
        char = q.get("character_group_change", 0)
        pp = plot_by_shot.get(sid, {})
        plot = pp.get("plot_change", pp.get("plot_change_score", 0))
        scene_score = round(W[0] * loc + W[1] * char + W[2] * plot)
        merged.append(
            {
                "shot_id": sid,
                "boundary_index": i,
                "timestamp_ms": shot["end_ms"],
                "location_change": loc,
                "character_group_change": char,
                "plot_change_score": plot,
                "scene_score": scene_score,
            }
        )

    # Greedy: rank by scene_score desc, pick top K with min_distance
    target_count = max(3, int(len(shots) * INTENSITY_RATIOS[args.intensity]))
    ranked = sorted(merged, key=lambda b: b["scene_score"], reverse=True)
    selected = []
    for b in ranked:
        if b["scene_score"] == 0:
            continue
        if any(abs(b["timestamp_ms"] - s["timestamp_ms"]) < MIN_DISTANCE_MS for s in selected):
            continue
        selected.append(b)
        if len(selected) >= target_count:
            break
    selected.sort(key=lambda b: b["timestamp_ms"])

    # Candidate boundaries (the selected cut points)
    candidate_boundaries = []
    for s in selected:
        m, sec = divmod(s["timestamp_ms"], 60000)
        candidate_boundaries.append(
            {
                "shot_id": s["shot_id"],
                "boundary_index": s["boundary_index"],
                "timestamp_ms": s["timestamp_ms"],
                "timestamp_readable": f"{int(m):02d}:{sec / 1000:05.2f}",
                "scene_score": s["scene_score"],
                "location_change": s["location_change"],
                "character_group_change": s["character_group_change"],
                "plot_change_score": s["plot_change_score"],
            }
        )

    # Build final scenes from selected boundaries
    final_scenes = []
    scene_start, scene_start_shot = shots[0]["start_ms"], shots[0]["shot_id"]
    for b in selected:
        final_scenes.append(
            {
                "start_shot": scene_start_shot,
                "end_shot": b["shot_id"],
                "start_ms": scene_start,
                "end_ms": b["timestamp_ms"],
                "scene_score": b["scene_score"],
            }
        )
        next_idx = b["boundary_index"] + 1
        scene_start = shots[next_idx]["start_ms"] if next_idx < len(shots) else b["timestamp_ms"]
        scene_start_shot = shots[next_idx]["shot_id"] if next_idx < len(shots) else b["shot_id"]
    final_scenes.append(
        {
            "start_shot": scene_start_shot,
            "end_shot": shots[-1]["shot_id"],
            "start_ms": scene_start,
            "end_ms": shots[-1]["end_ms"],
            "scene_score": 0,
        }
    )

    output = {
        "video_id": "SceneSeg_Test1",
        "shot_count": len(shots),
        "mode": args.mode,
        "weights": {"location": W[0], "character": W[1], "plot": W[2]},
        "intensity": args.intensity,
        "target_count": target_count,
        "min_distance_ms": MIN_DISTANCE_MS,
        "merged_scores": merged,
        "candidate_boundaries": candidate_boundaries,
        "final_scenes": final_scenes,
    }
    with open(args.out, "w", encoding="utf-8") as f:
        json.dump(output, f, ensure_ascii=False, indent=2)

    print(f"Mode: {args.mode}, Intensity: {args.intensity}")
    print(f"Target: {target_count}, Selected: {len(selected)} boundaries")
    for cb in candidate_boundaries:
        print(f"  {cb['shot_id']} @ {cb['timestamp_readable']}  score={cb['scene_score']}")


if __name__ == "__main__":
    main()
