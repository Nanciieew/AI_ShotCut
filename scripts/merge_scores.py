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
    p.add_argument("--threshold", type=int, default=50)
    p.add_argument("--min-scene-s", type=int, default=30)
    p.add_argument(
        "--shots",
        default="data/local_validation/projects/local_validation/videos/SceneSeg_Test1/artifacts/omnishotcut/0.1.0/shots.json",
    )
    p.add_argument("--vlm", default="data/sceneseg_test1_qwen_vlm_scores.json")
    p.add_argument("--plot", default="data/sceneseg_test1_deepseek_plot_v2.json")
    p.add_argument("--out", default="data/sceneseg_test1_final_result.json")
    args = p.parse_args()

    W = compute_weights(args.mode, args.L, args.C, args.P)
    MIN_SCENE_MS = args.min_scene_s * 1000
    THRESHOLD = args.threshold

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

    # Merge
    merged, final_scenes = [], []
    scene_start, scene_start_shot = shots[0]["start_ms"], shots[0]["shot_id"]

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
                "location_change": loc,
                "character_group_change": char,
                "plot_change_score": plot,
                "scene_score": scene_score,
            }
        )

        dur = shot["end_ms"] - scene_start
        if scene_score >= THRESHOLD and dur >= MIN_SCENE_MS:
            final_scenes.append(
                {
                    "start_shot": scene_start_shot,
                    "end_shot": sid,
                    "start_ms": scene_start,
                    "end_ms": shot["end_ms"],
                    "scene_score": scene_score,
                }
            )
            scene_start = shots[i + 1]["start_ms"]
            scene_start_shot = shots[i + 1]["shot_id"]

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
        "threshold": THRESHOLD,
        "min_scene_ms": MIN_SCENE_MS,
        "merged_scores": merged,
        "final_scenes": final_scenes,
    }
    with open(args.out, "w", encoding="utf-8") as f:
        json.dump(output, f, ensure_ascii=False, indent=2)

    print(f"Mode: {args.mode}, Weights: ({W[0]:.2f}, {W[1]:.2f}, {W[2]:.2f})")
    print(f"Scenes: {len(final_scenes)}")
    for s in final_scenes:
        m1, s1 = divmod(s["start_ms"], 60000)
        m2, s2 = divmod(s["end_ms"], 60000)
        print(
            f"  {s['start_shot']}→{s['end_shot']}: "
            f"[{int(m1)}:{s1 / 1000:04.1f}-{int(m2)}:{s2 / 1000:04.1f}] "
            f"({int((s['end_ms'] - s['start_ms']) / 1000)}s) score={s['scene_score']}"
        )


if __name__ == "__main__":
    main()
