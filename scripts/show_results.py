"""Show pipeline results."""

import json
import os
import sys

vid_dir = sys.argv[1] if len(sys.argv) > 1 else "data/projects/default/videos/f17d446b1731410d"
result_path = os.path.join(vid_dir, "artifacts/final/1.0.0/final_result.json")

if not os.path.exists(result_path):
    print(f"No result found at {result_path}")
    sys.exit(1)

with open(result_path, encoding="utf-8") as f:
    d = json.load(f)

print("=== FINAL RESULT ===")
print(f"Video ID: {d['video_id']}")
print(f"Shots: {len(d['shots'])}")
print(f"Subtitles: {len(d['subtitle_segments'])} segments")
print(f"Scenes: {len(d['scenes'])}")
print(f"Candidate boundaries: {len(d['candidate_boundaries'])}")
print()

print("=== SCENES ===")
for s in d["scenes"]:
    ms = s["start_ms"]
    ems = s["end_ms"]
    print(
        f"  {s['start_shot']} -> {s['end_shot']}  "
        f"[{ms // 60000:02d}:{(ms % 60000) // 1000:02d} - "
        f"{ems // 60000:02d}:{(ems % 60000) // 1000:02d}]  score={s['scene_score']}"
    )
print()

print("=== ARTIFACTS TREE ===")
base = os.path.join(vid_dir, "artifacts")
for root, dirs, files in os.walk(base):
    level = root.replace(base, "").count(os.sep)
    indent = "  " * level
    print(f"{indent}{os.path.basename(root)}/")
    for f in sorted(files):
        fp = os.path.join(root, f)
        size = os.path.getsize(fp)
        if size > 1024 * 1024:
            size_str = f"{size / 1024 / 1024:.1f} MB"
        elif size > 1024:
            size_str = f"{size / 1024:.1f} KB"
        else:
            size_str = f"{size} B"
        print(f"{indent}  {f} ({size_str})")
