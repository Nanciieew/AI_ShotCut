#!/usr/bin/env python3
"""End-to-end: raw video → OmniShotCutAdapter → normalized output.

Usage: python scripts/experiments/omnishotcut/run_adapter.py

Produces: tests/fixtures/normalized_outputs/omnishotcut/*.shots.json
"""

import json, os, sys, time
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent.parent
VIDEOS_DIR = PROJECT_ROOT / "tests" / "fixtures" / "videos" / "omnishotcut"
OUT_DIR = PROJECT_ROOT / "tests" / "fixtures" / "normalized_outputs" / "omnishotcut"

# Set up FFmpeg PATH before any imports
import imageio_ffmpeg
_FF_DIR = Path(imageio_ffmpeg.get_ffmpeg_exe()).parent
os.environ["PATH"] = str(_FF_DIR) + os.pathsep + os.environ.get("PATH", "")

from models.omnishotcut.adapter import OmniShotCutAdapter


def main() -> int:
    videos = sorted(VIDEOS_DIR.glob("*.mp4"))
    if not videos:
        print(f"No videos in {VIDEOS_DIR}")
        return 0

    OUT_DIR.mkdir(parents=True, exist_ok=True)

    print("Loading OmniShotCutAdapter ...")
    adapter = OmniShotCutAdapter()
    adapter.load()

    results = []
    for vp in videos:
        vname = vp.name
        vpath = str(vp)
        vbase = vname.rsplit(".", 1)[0]

        print(f"\n--- {vname} ---")
        t0 = time.monotonic()

        output = adapter.predict({
            "schema_version": "1.0",
            "task_id": f"test_{vbase}",
            "video_id": f"test_{vbase}",
            "model": {"name": "omnishotcut", "version": "0.1.0"},
            "input": {"video_uri": vpath},
            "parameters": {"mode": "clean_shot"},
        })

        rt = time.monotonic() - t0

        if output["status"] == "SUCCEEDED":
            m = output["metrics"]
            shot_count = m["shot_count"]
            print(f"  Status: OK  shots={shot_count} "
                  f"(raw={m['shot_count_raw']}) "
                  f"fp_removed={m['false_positives_removed']} runtime={rt:.1f}s")
            if m.get("frame_diff", {}).get("false_positives_removed", 0) > 0:
                print(f"  Frame-diff removed {m['frame_diff']['false_positives_removed']} FP boundaries")

            # Save task-level result per IO_Rule §2
            task_path = OUT_DIR / f"{vbase}.task_result.json"
            task_path.write_text(json.dumps(output, indent=2, ensure_ascii=False), encoding="utf-8")

            # Save shots artifact per IO_Rule §4.1
            shots_path = OUT_DIR / f"{vbase}.shots.json"
            shots_artifact = {
                "video_id": f"test_{vbase}",
                "model": {"name": "omnishotcut", "version": "0.1.0"},
                "shots": adapter._last_shots,
            }
            shots_path.write_text(json.dumps(shots_artifact, indent=2, ensure_ascii=False), encoding="utf-8")
            out_path = task_path
        else:
            print(f"  Status: FAIL  {output['error']['code']}: {output['error']['message']}")
            out_path = OUT_DIR / f"{vbase}.error.json"
            out_path.write_text(json.dumps(output, indent=2, ensure_ascii=False), encoding="utf-8")

        results.append({"video": vname, "status": output["status"], "output": out_path.name})

    # Summary
    print(f"\n{'='*60}")
    for r in results:
        print(f"  {r['video']:<30} {r['status']}")
    print(f"\nOutputs: {OUT_DIR}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
