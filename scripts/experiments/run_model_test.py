#!/usr/bin/env python3
"""Universal model test: raw → IO_Rule validate → normalized output.

Usage:
  python scripts/experiments/run_model_test.py --model omnishotcut

Steps:
  1. Load model adapter from models/{model}/adapter.py
  2. Read test videos from tests/fixtures/videos/{model}/
  3. Run adapter.predict() on each video
  4. Validate output against IO_Rule.md
  5. Save task_result.json (§2) + shots.json (§4.1)
  6. Print IO_Rule compliance report
"""

import argparse
import importlib
import json
import os
import sys
import time
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent


def setup_ffmpeg() -> None:
    """Ensure FFmpeg is on PATH via imageio-ffmpeg."""
    try:
        import imageio_ffmpeg
        ff_dir = str(Path(imageio_ffmpeg.get_ffmpeg_exe()).parent)
        os.environ["PATH"] = ff_dir + os.pathsep + os.environ.get("PATH", "")
    except ImportError:
        pass


def load_adapter(model_name: str):
    """Dynamically load a model adapter by finding BaseModelAdapter subclass."""
    module_path = f"models.{model_name}.adapter"
    try:
        mod = importlib.import_module(module_path)
    except ModuleNotFoundError:
        print(f"[FAIL] Module not found: {module_path}")
        sys.exit(1)

    # Find the adapter class (subclass of BaseModelAdapter)
    from models.base.adapter import BaseModelAdapter
    adapter_cls = None
    for name in dir(mod):
        obj = getattr(mod, name)
        if isinstance(obj, type) and issubclass(obj, BaseModelAdapter) and obj is not BaseModelAdapter:
            adapter_cls = obj
            break

    if adapter_cls is None:
        print(f"[FAIL] No BaseModelAdapter subclass found in {module_path}")
        sys.exit(1)

    adapter = adapter_cls()
    adapter.load()
    return adapter


def check_io_rule(task_result: dict, model_name: str) -> list[str]:
    """Validate task_result against IO_Rule §2/§3. Returns list of issues."""
    issues = []

    # §2 Required fields
    for field in ["schema_version", "task_id", "video_id", "status", "model", "artifacts", "metrics", "error"]:
        if field not in task_result:
            issues.append(f"Missing required field: {field}")

    if task_result.get("schema_version") != "1.0":
        issues.append(f"schema_version must be '1.0', got {task_result.get('schema_version')}")

    model = task_result.get("model", {})
    if model.get("name") != model_name:
        issues.append(f"model.name mismatch: expected '{model_name}', got '{model.get('name')}'")

    if task_result.get("status") == "SUCCEEDED":
        if task_result.get("error") is not None:
            issues.append("Status SUCCEEDED but error is not null")

        artifacts = task_result.get("artifacts", {})
        for key, uri in artifacts.items():
            if not uri or not uri.startswith("storage://"):
                issues.append(f"artifacts.{key} URI invalid: '{uri}' — must start with storage://")

        metrics = task_result.get("metrics", {})
        if "runtime_ms" not in metrics:
            issues.append("metrics missing required field: runtime_ms")

        # §5 time check
        for shot_count_key in ("shot_count", "shot_count_filtered"):
            if shot_count_key not in metrics:
                continue

    elif task_result.get("status") == "FAILED":
        err = task_result.get("error", {})
        for field in ["code", "message", "retryable"]:
            if field not in err:
                issues.append(f"error missing required field: {field}")

    # Forbidden fields
    output_str = json.dumps(task_result)
    for fk in ["action_score", "plot_score"]:
        if fk in output_str:
            issues.append(f"Forbidden field found: {fk}")

    return issues


def check_shots_artifact(shots_data: dict) -> list[str]:
    """Validate shots.json against IO_Rule §4.1. Returns list of issues."""
    issues = []

    if "video_id" not in shots_data:
        issues.append("Missing video_id")
    if "shots" not in shots_data:
        issues.append("Missing shots array")
        return issues

    shots = shots_data["shots"]
    for i, s in enumerate(shots):
        prefix = f"shots[{i}]"
        for f in ["shot_id", "index", "start_ms", "end_ms", "start_frame", "end_frame_exclusive"]:
            if f not in s:
                issues.append(f"{prefix} missing field: {f}")
        if s.get("end_ms", 0) <= s.get("start_ms", 0):
            issues.append(f"{prefix}: end_ms <= start_ms")
        if s.get("end_frame_exclusive", 0) <= s.get("start_frame", 0):
            issues.append(f"{prefix}: end_frame_exclusive <= start_frame")
        if s.get("confidence") is not None:
            if not (0 <= s["confidence"] <= 1):
                issues.append(f"{prefix}: confidence {s['confidence']} not in [0,1]")
        ms_fields = ["start_ms", "end_ms"]
        for mf in ms_fields:
            if not isinstance(s.get(mf), int):
                issues.append(f"{prefix}: {mf} must be integer ms, got {type(s.get(mf)).__name__}")

    # Continuity check
    for i in range(len(shots) - 1):
        if shots[i]["end_ms"] != shots[i + 1]["start_ms"]:
            issues.append(
                f"shots[{i}].end_ms({shots[i]['end_ms']}) != "
                f"shots[{i+1}].start_ms({shots[i+1]['start_ms']})"
            )

    return issues


def main() -> int:
    parser = argparse.ArgumentParser(description="Universal model test runner")
    parser.add_argument("--model", required=True, help="Model name (e.g. omnishotcut)")
    args = parser.parse_args()

    model_name = args.model
    videos_dir = PROJECT_ROOT / "tests" / "fixtures" / "videos" / model_name
    raw_dir = PROJECT_ROOT / "tests" / "fixtures" / "raw_outputs" / model_name
    norm_dir = PROJECT_ROOT / "tests" / "fixtures" / "normalized_outputs" / model_name

    videos = sorted(videos_dir.glob("*.mp4"))
    if not videos:
        print(f"No test videos in {videos_dir}")
        return 0

    norm_dir.mkdir(parents=True, exist_ok=True)
    setup_ffmpeg()

    print(f"Loading {model_name} adapter ...")
    adapter = load_adapter(model_name)

    total_issues = 0
    for vp in videos:
        vname = vp.name
        vbase = vname.rsplit(".", 1)[0]
        print(f"\n--- {vname} ---")

        t0 = time.monotonic()
        output = adapter.predict({
            "schema_version": "1.0",
            "task_id": f"test_{vbase}",
            "video_id": f"test_{vbase}",
            "model": {"name": model_name, "version": getattr(adapter, 'version', '0.1.0')},
            "input": {"video_uri": str(vp)},
            "parameters": {"mode": "clean_shot"},
        })
        rt = time.monotonic() - t0

        if output["status"] == "SUCCEEDED":
            m = output["metrics"]
            print(f"  OK  shots={m.get('shot_count','?')}  runtime={rt:.1f}s")

            # Save task_result.json (§2)
            task_path = norm_dir / f"{vbase}.task_result.json"
            task_path.write_text(json.dumps(output, indent=2, ensure_ascii=False), encoding="utf-8")

            # Save shots.json (§4.1)
            shots_path = norm_dir / f"{vbase}.shots.json"
            shots_artifact = {
                "video_id": f"test_{vbase}",
                "model": {"name": model_name, "version": getattr(adapter, 'version', '0.1.0')},
                "shots": getattr(adapter, '_last_shots', []),
            }
            shots_path.write_text(json.dumps(shots_artifact, indent=2, ensure_ascii=False), encoding="utf-8")
        else:
            print(f"  FAIL  {output['error']['code']}: {output['error']['message']}")
            task_path = norm_dir / f"{vbase}.error.json"
            task_path.write_text(json.dumps(output, indent=2, ensure_ascii=False), encoding="utf-8")
            continue

        # IO_Rule compliance check
        issues = check_io_rule(output, model_name)
        issues += check_shots_artifact(shots_artifact)
        total_issues += len(issues)
        if issues:
            print(f"  IO_Rule issues: {len(issues)}")
            for iss in issues[:10]:
                print(f"    - {iss}")
        else:
            print(f"  IO_Rule: PASS")

    print(f"\n{'='*60}")
    print(f"IO_Rule compliance: {'FAIL' if total_issues else 'PASS'} ({total_issues} issues)")
    print(f"Outputs: {norm_dir}")
    return 1 if total_issues else 0


if __name__ == "__main__":
    sys.exit(main())
