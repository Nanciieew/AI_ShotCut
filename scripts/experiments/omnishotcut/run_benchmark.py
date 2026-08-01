#!/usr/bin/env python3
"""OmniShotCut benchmark with frame-diff validation.

Usage: python scripts/experiments/omnishotcut/run_benchmark.py

Outputs:
  tests/fixtures/raw_outputs/omnishotcut/   — raw model output + confidences
  tests/fixtures/raw_outputs/omnishotcut/   — frame-diff filtered output
"""

import importlib.util
import json
import os
import re
import sys
import time
from pathlib import Path
from subprocess import run as sub_run

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent.parent
OUT_DIR = PROJECT_ROOT / "tests" / "fixtures" / "raw_outputs" / "omnishotcut"

# FFmpeg/ffprobe from imageio-ffmpeg — set PATH BEFORE model import
import imageio_ffmpeg

_FF_DIR = Path(imageio_ffmpeg.get_ffmpeg_exe()).parent
_FFMPEG = str(_FF_DIR / "ffmpeg.exe")
_FFPROBE = str(_FF_DIR / "ffprobe.exe")
if not os.path.exists(_FFPROBE):
    import shutil

    shutil.copy2(_FFMPEG, _FFPROBE)
os.environ["PATH"] = str(_FF_DIR) + os.pathsep + os.environ.get("PATH", "")

# Import frame_diff directly (avoid cascade requiring pydantic)
_spec = importlib.util.spec_from_file_location(
    "frame_diff", str(PROJECT_ROOT / "models" / "omnishotcut" / "frame_diff.py")
)
_fd = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_fd)
FrameDiffValidator = _fd.FrameDiffValidator


def _ffprobe(args: list[str]) -> str:
    r = sub_run([_FFPROBE] + args, capture_output=True, text=True)
    if r.returncode != 0:
        raise RuntimeError(f"ffprobe failed: {r.stderr}")
    return r.stdout


def get_fps(video_path: str) -> tuple[int, int]:
    try:
        out = _ffprobe(
            [
                "-v",
                "quiet",
                "-select_streams",
                "v:0",
                "-show_entries",
                "stream=r_frame_rate",
                "-of",
                "json",
                video_path,
            ]
        )
        return tuple(map(int, json.loads(out)["streams"][0]["r_frame_rate"].split("/")))
    except Exception:
        pass
    r = sub_run([str(_FFMPEG), "-i", video_path], capture_output=True, text=True)
    for line in r.stderr.split("\n"):
        m = re.search(r"(\d+)\s*fps", line)
        if m:
            return int(m.group(1)), 1
    return 24000, 1001


def get_frame_count(video_path: str) -> int:
    try:
        out = _ffprobe(
            [
                "-v",
                "quiet",
                "-select_streams",
                "v:0",
                "-count_frames",
                "-show_entries",
                "stream=nb_read_frames",
                "-of",
                "json",
                video_path,
            ]
        )
        return int(json.loads(out)["streams"][0]["nb_read_frames"])
    except Exception:
        pass
    return -1


def main() -> int:
    fixtures_dir = PROJECT_ROOT / "tests" / "fixtures" / "videos" / "omnishotcut"
    videos = sorted(fixtures_dir.glob("*.mp4"))
    if not videos:
        print(f"No videos in {fixtures_dir}")
        return 0

    OUT_DIR.mkdir(parents=True, exist_ok=True)

    # Load model
    print("Loading OmniShotCut ...")
    import omnishotcut

    model = omnishotcut.load(
        str(PROJECT_ROOT / "model_store/omnishotcut/1.0.0/OmniShotCut_ckpt.pth")
    )

    validator = FrameDiffValidator(mad_threshold=5.0, hist_threshold=0.95)
    results = []

    for vp in videos:
        vname = vp.name
        vpath = str(vp)
        print(f"\n--- {vname} ({vp.stat().st_size / 1024 / 1024:.1f} MB) ---")

        num, den = get_fps(vpath)
        fc = get_frame_count(vpath)
        dur = round(fc * den / num, 1) if fc > 0 else -1

        # Raw inference
        t0 = time.monotonic()
        err, raw, confs = None, None, None
        try:
            raw, confs = model.inference(vpath, mode="clean_shot")
        except Exception as e:
            err = str(e)
        rt = time.monotonic() - t0

        # Frame-diff validation
        fd_report = None
        filtered = raw
        fd_stats = {}
        if raw and len(raw) > 1:
            fd_report = validator.validate(vpath, raw)
            filtered = validator.filter_by_diff(raw, fd_report)
            fd_stats = fd_report.stats
            fp_count = fd_stats.get("false_positive_count", 0)
            if fp_count > 0:
                print(
                    f"  [FRAME-DIFF] Filtered {fp_count} boundary(s), {len(raw)}→{len(filtered)} shots"
                )
                for b in fd_report.boundaries:
                    if b.is_likely_false:
                        print(f"    frame {b.frame_idx}: MAD={b.mad:.1f} — removed")

        raw_count = len(raw) if raw else 0
        filt_count = len(filtered) if filtered else 0
        status = "OK" if err is None else f"FAIL: {err[:60]}"
        print(
            f"  fps={num}/{den} dur={dur}s runtime={rt:.1f}s shots_raw={raw_count} shots_filtered={filt_count} {status}"
        )

        entry = {
            "video": vname,
            "fps_num": num,
            "fps_den": den,
            "fps": round(num / den, 4),
            "frame_count": fc,
            "duration_s": dur,
            "mode": "clean_shot",
            "runtime_s": round(rt, 2),
            "error": err,
            "shot_count_raw": raw_count,
            "shot_count_filtered": filt_count,
            "raw_ranges": raw,
            "confidences": confs,
            "filtered_ranges": filtered,
            "frame_diff_stats": fd_stats,
            "frame_diff_boundaries": [
                {
                    "frame": b.frame_idx,
                    "mad": b.mad,
                    "hist_corr": b.hist_corr,
                    "flagged": b.is_likely_false,
                }
                for b in fd_report.boundaries
            ]
            if fd_report
            else [],
        }
        out_path = OUT_DIR / f"{vname.rsplit('.', 1)[0]}_raw.json"
        out_path.write_text(json.dumps(entry, indent=2, ensure_ascii=False), encoding="utf-8")
        results.append(entry)

    # Summary
    summary = OUT_DIR / "_summary.json"
    summary.write_text(json.dumps(results, indent=2, ensure_ascii=False), encoding="utf-8")

    print(f"\n{'=' * 60}")
    print(f"{'Video':<30} {'Raw':>5} {'Filt':>5} {'Runtime':>8} {'Status'}")
    print(f"{'=' * 60}")
    for r in results:
        status = "OK" if r["error"] is None else "FAIL"
        print(
            f"{r['video']:<30} {r['shot_count_raw']:>5} {r['shot_count_filtered']:>5} {r['runtime_s']:>7.1f}s {status}"
        )
    print(f"\nSummary: {summary}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
