#!/usr/bin/env python3
"""
OmniShotCut environment check script.

Checks every prerequisite and outputs a structured JSON report.
Fails early with clear fix commands — does NOT fake success.

Usage:
  python scripts/check_omnishotcut_environment.py
  python scripts/check_omnishotcut_environment.py --json > env_report.json
"""

import argparse
import json
import platform
import shutil
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parent.parent


def run_cmd(cmd: list[str], timeout: int = 30) -> tuple[int, str, str]:
    """Run a command and return (exit_code, stdout, stderr)."""
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
        return r.returncode, r.stdout.strip(), r.stderr.strip()
    except FileNotFoundError:
        return -1, "", f"command not found: {cmd[0]}"
    except subprocess.TimeoutExpired:
        return -2, "", "command timed out"


def check_python() -> dict:
    result: dict[str, Any] = {"check": "Python version"}
    result["version"] = platform.python_version()
    major, minor = platform.python_version_tuple()
    result["ok"] = (int(major), int(minor)) >= (3, 10)
    if not result["ok"]:
        result["fix"] = "Install Python 3.10+ from https://www.python.org/downloads/"
    return result


def check_ffmpeg() -> dict:
    result: dict[str, Any] = {"check": "FFmpeg on PATH"}
    path = shutil.which("ffmpeg")
    if path:
        code, out, err = run_cmd(["ffmpeg", "-version"])
        result["path"] = path
        result["ok"] = True
        # Extract version line
        if out:
            result["version_info"] = out.split("\n")[0] if out else "unknown"
    else:
        result["ok"] = False
        result["path"] = None
        result["fix"] = (
            "Install FFmpeg: https://ffmpeg.org/download.html "
            "or 'winget install ffmpeg' on Windows"
        )
    return result


def check_pytorch() -> dict:
    result: dict[str, Any] = {"check": "PyTorch"}
    try:
        import torch

        result["version"] = torch.__version__
        result["ok"] = True
    except ImportError:
        result["ok"] = False
        result["fix"] = (
            "pip install torch torchvision --index-url https://download.pytorch.org/whl/cu121"
        )
        return result

    result["cuda_available"] = torch.cuda.is_available()
    if torch.cuda.is_available():
        result["cuda_version"] = torch.version.cuda
        result["gpu_count"] = torch.cuda.device_count()
        gpu_names = [torch.cuda.get_device_name(i) for i in range(torch.cuda.device_count())]
        result["gpu_names"] = gpu_names
    else:
        result["gpu_names"] = []
        result["note"] = "CPU only — inference will be slow for long videos"

    return result


def check_omnishotcut_import() -> dict:
    result: dict[str, Any] = {"check": "OmniShotCut import"}
    for name in ("omnishotcut", "OmniShotCut", "OmniShotCut"):
        try:
            mod = __import__(name)
            result["ok"] = True
            result["import_name"] = name
            result["module_path"] = getattr(mod, "__file__", "unknown")
            if hasattr(mod, "__version__"):
                result["version"] = mod.__version__
            return result
        except ImportError:
            continue

    result["ok"] = False
    result["import_name"] = None
    result["fix"] = (
        "pip install git+https://github.com/UVA-Computer-Vision-Lab/"
        "OmniShotCut.git@<COMMIT_HASH>"
    )
    return result


def check_model_weights() -> dict:
    result: dict[str, Any] = {"check": "Model weights accessible"}
    model_store = PROJECT_ROOT / "model_store" / "omnishotcut" / "1.0.0"
    weights_files = list(model_store.glob("*.pth")) + list(model_store.glob("*.pt")) + list(model_store.glob("*.ckpt"))

    if weights_files:
        wf = weights_files[0]
        result["ok"] = True
        result["weight_file"] = str(wf.relative_to(PROJECT_ROOT))
        result["size_bytes"] = wf.stat().st_size
    else:
        result["ok"] = False
        result["weight_file"] = None
        result["fix"] = (
            f"Download model weights into: {model_store}\n"
            "  Reference: models/omnishotcut/README.md §权重"
        )
    return result


def check_weights_license() -> dict:
    result: dict[str, Any] = {"check": "Weights license verified"}
    result["ok"] = False
    result["status"] = "UNKNOWN — must be verified before commercial use"
    result["fix"] = "See models/registry.yaml → omnishotcut.weights_license"
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description="OmniShotCut environment check")
    parser.add_argument("--json", action="store_true", help="Output JSON")
    args = parser.parse_args()

    checks: list[dict] = []
    errors = 0

    for fn in [
        check_python,
        check_ffmpeg,
        check_pytorch,
        check_omnishotcut_import,
        check_model_weights,
        check_weights_license,
    ]:
        try:
            r = fn()
            checks.append(r)
            if not r["ok"]:
                errors += 1
        except Exception as e:
            checks.append({"check": fn.__name__, "ok": False, "error": str(e)})
            errors += 1

    report = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "project_root": str(PROJECT_ROOT),
        "total_checks": len(checks),
        "passed": len(checks) - errors,
        "failed": errors,
        "checks": checks,
    }

    if args.json:
        print(json.dumps(report, indent=2, ensure_ascii=False))
    else:
        # Human-readable output
        print("=" * 60)
        print("OmniShotCut — Environment Check")
        print("=" * 60)
        for c in checks:
            icon = "[OK]" if c.get("ok") else "[FAIL]"
            print(f"\n{icon} {c['check']}")
            for k, v in c.items():
                if k in ("check", "ok"):
                    continue
                if k == "fix" and c.get("ok"):
                    continue
                print(f"    {k}: {v}")
        print(f"\n{'=' * 60}")
        print(f"Passed: {report['passed']}/{report['total_checks']}")
        if errors:
            print(f"\n{errors} check(s) FAILED. Fix them before running inference.")
            print("Run each 'fix' command listed above, then re-run this script.")
        else:
            print("All checks passed. Ready for raw inference.")

    return 1 if errors else 0


if __name__ == "__main__":
    sys.exit(main())
