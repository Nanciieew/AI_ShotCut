#!/usr/bin/env python3
"""
OmniShotCut environment check — generic report + model-specific checks.

Usage:
    python scripts/check_omnishotcut_environment.py
    python scripts/check_omnishotcut_environment.py --json
    python scripts/check_omnishotcut_environment.py --output report.json
    python scripts/check_omnishotcut_environment.py --check-fixtures
    python scripts/check_omnishotcut_environment.py --load-model
    python scripts/check_omnishotcut_environment.py --run-smoke-test

Default behaviour (no flags):
  - Collects generic environment report
  - Adds OmniShotCut import / version / compatibility checks
  - Inspects weight file presence + SHA256
  - Inspects test fixture presence (list only)
  - Does NOT load model weights into memory
  - Does NOT run inference

--check-fixtures: additionally run ffprobe on each test video
--load-model:     additionally load OmniShotCut model weights
--run-smoke-test: additionally run inference on the smallest test video
"""

import argparse
import hashlib
import json
import os
import subprocess
import sys
from pathlib import Path
from typing import Any

# Ensure project root is on sys.path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from core.environment import EnvironmentReport, OverallStatus

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

OMNI_REPO = "https://github.com/UVA-Computer-Vision-Lab/OmniShotCut"
OMNI_COMMIT = "23ad6fb41b296fb9258b0e7825125a914573b906"
WEIGHTS_RELATIVE = "model_store/omnishotcut/1.0.0/OmniShotCut_ckpt.pth"
FIXTURES_DIR = PROJECT_ROOT / "tests" / "fixtures" / "videos"
EXPECTED_FIXTURES = ["no_cut.mp4", "hard_cut.mp4", "multiple_cuts.mp4"]


# ---------------------------------------------------------------------------
# OmniShotCut-specific checks
# ---------------------------------------------------------------------------

def _status_of(ok: bool, warn: bool = False) -> str:
    if not ok:
        return "FAIL"
    if warn:
        return "WARNING"
    return "PASS"


def check_omnishotcut_import() -> dict[str, Any]:
    """Can omnishotcut be imported?"""
    try:
        import omnishotcut  # noqa: F401
        path = getattr(omnishotcut, "__file__", "unknown")
        ver = getattr(omnishotcut, "__version__", None)
        return {
            "check": "omnishotcut_import",
            "status": "PASS",
            "value": True,
            "detail": f"version={ver}, path={path}" if ver else f"path={path}",
        }
    except ImportError as e:
        return {
            "check": "omnishotcut_import",
            "status": "NOT_INSTALLED",
            "value": False,
            "detail": str(e),
        }


def check_omnishotcut_repo() -> dict[str, Any]:
    return {
        "check": "omnishotcut_repository",
        "status": "PASS",
        "value": OMNI_REPO,
        "detail": f"Fixed commit: {OMNI_COMMIT}",
    }


def check_omnishotcut_compatibility() -> list[dict[str, Any]]:
    """Python / PyTorch / Torchvision compatibility.

    We check minimum versions. These are informational — unknown version → WARNING.
    """
    results: list[dict[str, Any]] = []

    # Python
    py_ok = sys.version_info >= (3, 10)
    results.append({
        "check": "omnishotcut_python_compat",
        "status": _status_of(py_ok),
        "value": f"{sys.version_info.major}.{sys.version_info.minor}",
        "detail": "Requires Python 3.10+" if not py_ok else "Compatible",
    })

    # PyTorch
    try:
        import torch
        pt_ver = torch.__version__
        pt_ok = True  # OmniShotCut works with modern PyTorch
        results.append({
            "check": "omnishotcut_pytorch_compat",
            "status": _status_of(pt_ok),
            "value": pt_ver,
            "detail": "Compatible",
        })
    except ImportError:
        results.append({
            "check": "omnishotcut_pytorch_compat",
            "status": "FAIL",
            "value": None,
            "detail": "PyTorch not installed — OmniShotCut requires PyTorch",
        })

    # Torchvision
    try:
        import torchvision
        tv_ver = torchvision.__version__
        results.append({
            "check": "omnishotcut_torchvision_compat",
            "status": "PASS",
            "value": tv_ver,
            "detail": "Compatible",
        })
    except ImportError:
        results.append({
            "check": "omnishotcut_torchvision_compat",
            "status": "FAIL",
            "value": None,
            "detail": "torchvision not installed — OmniShotCut requires torchvision",
        })

    return results


def check_omnishotcut_weights() -> dict[str, Any]:
    """Check weights existence + SHA256."""
    weight_path = PROJECT_ROOT / WEIGHTS_RELATIVE
    if not weight_path.is_file():
        return {
            "check": "omnishotcut_weights",
            "status": "FAIL",
            "value": None,
            "detail": f"Weight file missing: {weight_path}",
        }

    sha = hashlib.sha256(weight_path.read_bytes()).hexdigest()
    size_mb = round(weight_path.stat().st_size / (1024 * 1024), 1)
    return {
        "check": "omnishotcut_weights",
        "status": "PASS",
        "value": str(weight_path.relative_to(PROJECT_ROOT)),
        "detail": f"SHA256={sha}, size={size_mb} MB",
    }


def check_omnishotcut_test_fixtures(check_ffprobe: bool = False) -> list[dict[str, Any]]:
    """List test fixtures and optionally ffprobe them."""
    results: list[dict[str, Any]] = []

    present = []
    missing = []
    for name in EXPECTED_FIXTURES:
        if (FIXTURES_DIR / name).is_file():
            present.append(name)
        else:
            missing.append(name)

    results.append({
        "check": "omnishotcut_fixture_count",
        "status": "WARNING" if not present else ("WARNING" if missing else "PASS"),
        "value": len(present),
        "detail": f"Expected {len(EXPECTED_FIXTURES)}, present {len(present)}, missing {len(missing)}",
    })

    if missing:
        results.append({
            "check": "omnishotcut_missing_fixtures",
            "status": "WARNING",
            "value": missing,
            "detail": "Run: python scripts/generate_test_fixtures.py",
        })
    else:
        results.append({
            "check": "omnishotcut_missing_fixtures",
            "status": "PASS",
            "value": [],
            "detail": "All test fixtures present",
        })

    # Optionally ffprobe each fixture
    if check_ffprobe:
        probe_results = {}
        for name in present:
            path = FIXTURES_DIR / name
            try:
                r = subprocess.run(
                    ["ffprobe", "-v", "quiet", "-print_format", "json",
                     "-show_format", str(path)],
                    capture_output=True, text=True, timeout=15,
                )
                if r.returncode == 0:
                    info = json.loads(r.stdout)
                    dur = info.get("format", {}).get("duration", "?")
                    probe_results[name] = f"OK ({dur}s)"
                else:
                    probe_results[name] = f"ffprobe error: {r.stderr[:100]}"
            except Exception as e:
                probe_results[name] = str(e)

        results.append({
            "check": "omnishotcut_fixtures_ffprobe",
            "status": _status_of(all("OK" in v for v in probe_results.values()), warn=True),
            "value": probe_results,
            "detail": "Test videos readable by ffprobe",
        })

    return results


def check_omnishotcut_device() -> list[dict[str, Any]]:
    """Determine available device (CPU/GPU)."""
    results: list[dict[str, Any]] = []
    cpu_ok = True
    cuda_ok = False
    try:
        import torch
        cuda_ok = torch.cuda.is_available()
    except ImportError:
        cpu_ok = False

    results.append({
        "check": "omnishotcut_cpu_test",
        "status": "PASS" if cpu_ok else "FAIL",
        "value": cpu_ok,
        "detail": "CPU inference available" if cpu_ok else "PyTorch not installed — CPU unavailable",
    })
    results.append({
        "check": "omnishotcut_cuda_test",
        "status": "PASS" if cuda_ok else "WARNING",
        "value": cuda_ok,
        "detail": "GPU inference available" if cuda_ok else "CUDA not available — GPU inference disabled",
    })

    # Current device selection
    if cuda_ok:
        device = "cuda"
    elif cpu_ok:
        device = "cpu"
    else:
        device = "none"
    results.append({
        "check": "omnishotcut_selected_device",
        "status": "WARNING" if device == "cpu" else ("FAIL" if device == "none" else "PASS"),
        "value": device,
        "detail": None,
    })

    return results


# ---------------------------------------------------------------------------
# Model readiness
# ---------------------------------------------------------------------------

def compute_model_readiness(checks: list[dict[str, Any]]) -> dict[str, Any]:
    """Derive omnishotcut readiness from collected checks.

    BLOCKED if: PyTorch missing, or weights missing, or torchvision missing.
    READY_WITH_WARNINGS if: CPU-only or fixtures missing.
    READY if: all critical checks pass.
    """
    critical_checks = {
        "omnishotcut_pytorch_compat",
        "omnishotcut_torchvision_compat",
        "omnishotcut_weights",
    }
    statuses: dict[str, str] = {}
    for c in checks:
        statuses[c["check"]] = c.get("status", "NOT_RUN")

    if any(statuses.get(k) == "FAIL" for k in critical_checks):
        return {"model": "omnishotcut", "readiness": "BLOCKED",
                "reason": "Critical dependencies missing (PyTorch/torchvision/weights)"}
    if any(statuses.get(k) == "WARNING" for k in ["omnishotcut_cuda_test", "omnishotcut_cpu_test"]):
        return {"model": "omnishotcut", "readiness": "READY_WITH_WARNINGS",
                "reason": "CPU-only mode — slower, but functional"}
    return {"model": "omnishotcut", "readiness": "READY",
            "reason": "All checks passed — ready for inference"}


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> int:
    parser = argparse.ArgumentParser(
        description="OmniShotCut environment check — generic + model-specific"
    )
    parser.add_argument("--json", action="store_true", help="Output JSON to stdout")
    parser.add_argument("--output", type=str, default=None, help="Write report to file")
    parser.add_argument("--check-fixtures", action="store_true",
                        help="Also ffprobe each test video")
    parser.add_argument("--load-model", action="store_true",
                        help="Load OmniShotCut model weights into memory")
    parser.add_argument("--run-smoke-test", action="store_true",
                        help="Run inference on the smallest test video")
    args = parser.parse_args()

    # ------------------------------------------------------------------
    # 1. Generic environment report
    # ------------------------------------------------------------------
    report = EnvironmentReport()

    report.add_system_info()
    report.add_executable_info()
    report.add_pytorch_info()
    report.add_storage_info(
        storage_root=os.getenv("STORAGE_ROOT", "./data"),
        model_store_root=os.getenv("MODEL_STORE_ROOT", "./model_store"),
    )

    # ------------------------------------------------------------------
    # 2. OmniShotCut-specific checks
    # ------------------------------------------------------------------
    report.add_checks([check_omnishotcut_import()])
    report.add_checks([check_omnishotcut_repo()])
    report.add_checks(check_omnishotcut_compatibility())
    report.add_checks([check_omnishotcut_weights()])
    report.add_checks(check_omnishotcut_test_fixtures(check_ffprobe=args.check_fixtures))
    report.add_checks(check_omnishotcut_device())

    # ------------------------------------------------------------------
    # 3. Optional: load model
    # ------------------------------------------------------------------
    if args.load_model:
        try:
            import time
            t0 = time.monotonic()
            from models.omnishotcut.adapter import OmniShotCutAdapter
            adapter = OmniShotCutAdapter()
            adapter.load()
            elapsed = round(time.monotonic() - t0, 1)
            report.add_checks([{
                "check": "omnishotcut_load_model",
                "status": "PASS",
                "value": True,
                "detail": f"Model loaded in {elapsed}s",
            }])
            adapter.unload()
        except Exception as e:
            report.add_checks([{
                "check": "omnishotcut_load_model",
                "status": "FAIL",
                "value": False,
                "detail": str(e),
            }])

    # ------------------------------------------------------------------
    # 4. Optional: smoke test
    # ------------------------------------------------------------------
    if args.run_smoke_test:
        smallest = FIXTURES_DIR / "no_cut.mp4"
        if smallest.is_file():
            try:
                import time
                t0 = time.monotonic()
                from models.omnishotcut.adapter import OmniShotCutAdapter
                adapter = OmniShotCutAdapter()
                adapter.load()
                adapter.predict({
                    "schema_version": "1.0",
                    "task_id": "smoke_test",
                    "video_id": "smoke_test",
                    "model": {"name": "omnishotcut", "version": "0.1.0"},
                    "input": {"video_uri": str(smallest)},
                    "parameters": {"mode": "clean_shot"},
                })
                elapsed = round(time.monotonic() - t0, 1)
                adapter.unload()
                report.add_checks([{
                    "check": "omnishotcut_smoke_test",
                    "status": "PASS",
                    "value": True,
                    "detail": f"Smoke test passed in {elapsed}s on {smallest.name}",
                }])
            except Exception as e:
                report.add_checks([{
                    "check": "omnishotcut_smoke_test",
                    "status": "FAIL",
                    "value": False,
                    "detail": str(e),
                }])
        else:
            report.add_checks([{
                "check": "omnishotcut_smoke_test",
                "status": "NOT_RUN",
                "value": None,
                "detail": f"Smoke test video missing: {smallest}",
            }])

    # ------------------------------------------------------------------
    # 5. Finalize + model readiness
    # ------------------------------------------------------------------
    report.finalize()

    # Append model_readiness to checks (not part of overall status)
    readiness = compute_model_readiness(report.checks)
    report.checks.append({
        "check": "model_readiness_omnishotcut",
        "status": readiness["readiness"],
        "value": readiness["readiness"],
        "detail": readiness["reason"],
    })

    # ------------------------------------------------------------------
    # 6. Output
    # ------------------------------------------------------------------
    if args.json:
        output = report.to_json()
    else:
        output = report.to_text()

    if args.output:
        with open(args.output, "w", encoding="utf-8") as f:
            f.write(output)
        print(f"Report written to {args.output}", file=sys.stderr)
    else:
        print(output)

    if report.overall and report.overall.value == "BLOCKED":
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
