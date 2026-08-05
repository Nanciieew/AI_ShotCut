#!/usr/bin/env python3
"""Compare FFmpeg scene detection vs OmniShotCut on Complete_test1."""
import subprocess, json, re, sys

VIDEO = "Complete_test1_Output/01_normalized.mp4"
SHOTS_OMNI = "Complete_test1_Output/02_shots.json"

# Get FPS
r = subprocess.run(["ffprobe", "-v", "quiet", "-print_format", "json",
                     "-show_format", "-show_streams", VIDEO],
                    capture_output=True, text=True, timeout=15)
info = json.loads(r.stdout)
fps = 30
for s in info["streams"]:
    if s["codec_type"] == "video":
        n, d = s["r_frame_rate"].split("/")
        fps = int(n) / int(d); break
print(f"FPS: {fps}")

# Load OmniShotCut
with open(SHOTS_OMNI) as f:
    omni = json.load(f)["shots"]
omni_starts = {s["start_ms"] / 1000 for s in omni}
print(f"OmniShotCut: {len(omni)} shots")

for thr in [0.3, 0.4, 0.5]:
    cmd = ["ffmpeg", "-i", VIDEO,
           "-vf", f"select='gt(scene,{thr})',showinfo",
           "-vsync", "vfr", "-f", "null", "-"]
    r = subprocess.run(cmd, capture_output=True, text=True, timeout=300)
    import re
    times = sorted(set(float(t) for t in re.findall(r"pts_time:([\d.]+)", r.stderr)))

    tol = 0.5
    matched = sum(1 for t in times if any(abs(t - os) < tol for os in omni_starts))
    ffmpeg_only = len(times) - matched
    omni_only = len(omni) - 1 - matched
    rec = matched / (len(omni) - 1) * 100 if len(omni) > 1 else 0
    prec = matched / len(times) * 100 if times else 0
    print(f"thr={thr}: FFmpeg={len(times)} matched={matched} rec={rec:.1f}% prec={prec:.1f}% ffmpeg_only={ffmpeg_only} omni_only={omni_only}")
