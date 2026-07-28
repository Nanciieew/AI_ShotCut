#!/usr/bin/env python3
"""Run OmniShotCut benchmark on all available test videos.

Usage: python scripts/experiments/omnishotcut/run_benchmark.py
"""

import json, os, sys, time
from pathlib import Path
from subprocess import run as sub_run

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent.parent
OUT_DIR = PROJECT_ROOT / "tests" / "fixtures" / "raw_outputs" / "omnishotcut"

# FFmpeg/ffprobe from imageio-ffmpeg
import imageio_ffmpeg
_FF_DIR = Path(imageio_ffmpeg.get_ffmpeg_exe()).parent
_FFMPEG = str(_FF_DIR / "ffmpeg.exe")
_FFPROBE = str(_FF_DIR / "ffprobe.exe")
# Ensure the imageio binary dir has ffprobe.exe alias
if not os.path.exists(_FFPROBE):
    import shutil
    shutil.copy2(_FFMPEG, _FFPROBE)
os.environ["PATH"] = str(_FF_DIR) + os.pathsep + os.environ.get("PATH", "")


def get_fps(video_path: str) -> tuple[int, int]:
    r = sub_run([_FFPROBE,"-v","quiet","-select_streams","v:0","-show_entries","stream=r_frame_rate","-of","json",video_path], capture_output=True, text=True)
    num, den = map(int, json.loads(r.stdout)["streams"][0]["r_frame_rate"].split("/"))
    return num, den

def get_frame_count(video_path: str) -> int:
    r = sub_run([_FFPROBE,"-v","quiet","-select_streams","v:0","-count_frames","-show_entries","stream=nb_read_frames","-of","json",video_path], capture_output=True, text=True)
    return int(json.loads(r.stdout)["streams"][0]["nb_read_frames"])


def main() -> int:
    # Locate videos
    fixtures_dir = PROJECT_ROOT / "tests" / "fixtures" / "videos" / "omnishotcut"
    demo_dir = Path("C:/Users/Administrator/AppData/Local/Temp/omnishotcut-clone/__assets__")

    videos: list[Path] = sorted(fixtures_dir.glob("*.mp4"))
    if not videos:
        print(f"No videos in {fixtures_dir}, using demo videos...")
        videos = sorted(demo_dir.glob("demo_video*.mp4"))

    if not videos:
        print("No videos found. Place .mp4 in tests/fixtures/videos/omnishotcut/")
        return 0

    OUT_DIR.mkdir(parents=True, exist_ok=True)

    # Load model
    print("Loading OmniShotCut ...")
    import omnishotcut
    weight_path = str(PROJECT_ROOT / "model_store/omnishotcut/1.0.0/OmniShotCut_ckpt.pth")
    model = omnishotcut.load(weight_path)

    results = []
    for vp in videos:
        vname = vp.name
        print(f"\n--- {vname} ({vp.stat().st_size/1024/1024:.1f} MB) ---")

        num, den = get_fps(str(vp))
        fc = get_frame_count(str(vp))
        dur = round(fc * den / num, 1)

        t0 = time.monotonic()
        err = None
        raw = None
        try:
            raw = model.inference(str(vp), mode="clean_shot")
        except Exception as e:
            err = str(e)
        rt = time.monotonic() - t0

        entry = {
            "video": vname,
            "fps_num": num, "fps_den": den, "fps": round(num/den, 4),
            "frame_count": fc, "duration_s": dur,
            "mode": "clean_shot",
            "runtime_s": round(rt, 2),
            "shot_count": len(raw) if raw else 0,
            "error": err,
            "raw_ranges": raw,
        }
        out_path = OUT_DIR / f"{vname.rsplit('.',1)[0]}_raw.json"
        out_path.write_text(json.dumps(entry, indent=2, ensure_ascii=False), encoding="utf-8")

        status = "OK" if err is None else f"FAIL: {err[:60]}"
        print(f"  fps={num}/{den} frames={fc} dur={dur}s runtime={rt:.1f}s shots={len(raw) if raw else 0} {status}")

        results.append(entry)

    # Summary
    summary = OUT_DIR / "_summary.json"
    summary.write_text(json.dumps(results, indent=2, ensure_ascii=False), encoding="utf-8")

    print(f"\nSummary: {summary}")
    print(f"Outputs: {OUT_DIR}")
    return 0

if __name__ == "__main__":
    sys.exit(main())
