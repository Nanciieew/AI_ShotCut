#!/usr/bin/env python3
"""
OmniShotCut raw inference runner.

Runs the model against a video file and saves the raw output
BEFORE any Schema conversion — for inspection and contract design.

Usage:
  python models/omnishotcut/run_raw_inference.py \
      --input fixtures/videos/hard_cut.mp4 \
      --output sample_output.json

Step checklist:
  1. model weights loadable?
  2. CPU / GPU?
  3. raw input format?
  4. raw output format?
  5. end frame inclusive or exclusive?
  6. confidence values?
  7. runtime for ~10s video?
  8. VRAM usage?
  9. FFmpeg dependency?
"""

import argparse
import json
import sys
import time
from pathlib import Path

# ---------------------------------------------------------------------------
# PATH SETUP — add this project root so imports work from scripts/ too
# ---------------------------------------------------------------------------
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT))


def emit_answers(results: dict) -> None:
    """Print a human-readable summary of the checklist items."""
    print("\n" + "=" * 50)
    print("OmniShotCut — Raw Inference Checklist")
    print("=" * 50)

    fmt = "  {:<40} {}"
    for label, value in results.items():
        print(fmt.format(label, value))


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Run OmniShotCut raw inference and save output."
    )
    parser.add_argument(
        "--input",
        required=True,
        help="Path to input video (e.g. fixtures/videos/hard_cut.mp4)",
    )
    parser.add_argument(
        "--output",
        default="sample_output.json",
        help="Path where raw model output will be saved (default: sample_output.json)",
    )
    parser.add_argument(
        "--device",
        default="auto",
        help="Device override: auto, cpu, or cuda:0",
    )
    args = parser.parse_args()

    input_path = Path(args.input)
    if not input_path.is_absolute():
        input_path = (Path(__file__).parent / input_path).resolve()

    if not input_path.is_file():
        print(f"[FAIL] Input video not found: {input_path}")
        return 1

    results: dict[str, str] = {}

    # -----------------------------------------------------------------------
    # 1. Environment
    # -----------------------------------------------------------------------
    print("[CHECK] Python / PyTorch / CUDA / FFmpeg ...")

    import platform

    results["Python version"] = platform.python_version()

    try:
        import torch

        results["PyTorch version"] = torch.__version__
        results["CUDA available"] = str(torch.cuda.is_available())
        if torch.cuda.is_available():
            results["GPU name"] = torch.cuda.get_device_name(0)
            results["GPU count"] = str(torch.cuda.device_count())
        else:
            results["GPU name"] = "N/A (CPU only)"
    except ImportError as e:
        print(f"[FAIL] PyTorch not installed: {e}")
        print("  Fix: pip install torch torchvision --index-url https://download.pytorch.org/whl/cu121")
        return 1

    # -----------------------------------------------------------------------
    # 2. FFmpeg
    # -----------------------------------------------------------------------
    import shutil

    ffmpeg_path = shutil.which("ffmpeg")
    if ffmpeg_path is None:
        print("[FAIL] FFmpeg not found on PATH.")
        print("  Fix: install FFmpeg (https://ffmpeg.org/download.html)")
        return 1
    results["FFmpeg on PATH"] = ffmpeg_path

    # -----------------------------------------------------------------------
    # 3. OmniShotCut import
    # -----------------------------------------------------------------------
    print("[CHECK] OmniShotCut import ...")

    try:
        import omnishotcut  # noqa: F401

        results["OmniShotCut import"] = "OK"
    except ImportError:
        # If the package name differs, try common alternatives or report
        try:
            import OmniShotCut  # type: ignore[import-untyped] # noqa: F401

            results["OmniShotCut import"] = "OK (as OmniShotCut)"
        except ImportError:
            results["OmniShotCut import"] = (
                "FAIL — install from repository: "
                "pip install git+https://github.com/UVA-Computer-Vision-Lab/"
                "OmniShotCut.git@<COMMIT_HASH>"
            )
            print(f"[FAIL] {results['OmniShotCut import']}")
            emit_answers(results)
            return 1

    # -----------------------------------------------------------------------
    # 4. Select device
    # -----------------------------------------------------------------------
    if args.device == "auto":
        device = "cuda:0" if torch.cuda.is_available() else "cpu"
    else:
        device = args.device
    results["Device used"] = device

    # -----------------------------------------------------------------------
    # 5. Load model (timed)
    # -----------------------------------------------------------------------
    print(f"[LOAD] Loading OmniShotCut on {device} ...")

    try:
        t0 = time.monotonic()
        # --- USER: replace this with the actual load call ---
        # model = omnishotcut.load_model(device=device)
        # --- placeholder: raise so user knows to fill in ---
        raise NotImplementedError(
            "Replace this block with the actual OmniShotCut model load call.\n"
            "Example:\n"
            "   model = omnishotcut.load_model(device='cuda:0')\n"
            "   model.eval()"
        )
        load_ms = int((time.monotonic() - t0) * 1000)
        results["Model load time (ms)"] = str(load_ms)
    except NotImplementedError:
        print("[SKIP] Model load call is a placeholder — update load block in run_raw_inference.py")
        results["Model load time (ms)"] = "SKIP (placeholder)"

    # -----------------------------------------------------------------------
    # 6. Run inference (timed + VRAM)
    # -----------------------------------------------------------------------
    print(f"[INFER] Running inference on {input_path.name} ({input_path.stat().st_size} bytes) ...")

    if torch.cuda.is_available():
        torch.cuda.reset_peak_memory_stats()
        vram_before = torch.cuda.memory_allocated() / 1024**2

    try:
        t0 = time.monotonic()

        # --- USER: replace this with the actual inference call ---
        # raw_output = model.predict(str(input_path))
        raw_output = {
            "_placeholder": True,
            "_note": "Replace predict call in run_raw_inference.py with actual model invocation",
        }

        runtime_ms = int((time.monotonic() - t0) * 1000)
        results["Runtime (ms)"] = str(runtime_ms)
        results["Runtime (s)"] = f"{runtime_ms / 1000:.1f}"
    except Exception as e:
        print(f"[FAIL] Inference error: {e}")
        emit_answers(results)
        return 1

    # VRAM peak
    if torch.cuda.is_available():
        vram_after = torch.cuda.memory_allocated() / 1024**2
        peak_mb = torch.cuda.max_memory_allocated() / 1024**2
        results["VRAM before (MB)"] = f"{vram_before:.0f}"
        results["VRAM after (MB)"] = f"{vram_after:.0f}"
        results["VRAM peak (MB)"] = f"{peak_mb:.0f}"
    else:
        results["VRAM"] = "N/A (CPU)"

    # -----------------------------------------------------------------------
    # 7. Inspect raw output
    # -----------------------------------------------------------------------
    print("[INSPECT] Analyzing raw output structure ...")

    results["Raw output type"] = type(raw_output).__name__

    if isinstance(raw_output, dict):
        results["Top-level keys"] = ", ".join(sorted(raw_output.keys()))
    elif isinstance(raw_output, list):
        results["Output length"] = str(len(raw_output))
        if raw_output:
            results["First item type"] = type(raw_output[0]).__name__
            if isinstance(raw_output[0], dict):
                results["First item keys"] = ", ".join(sorted(raw_output[0].keys()))

    # Detect end-frame convention
    results["End frame convention"] = _detect_end_frame(raw_output)
    # Detect confidence
    results["Has confidence"] = _detect_confidence(raw_output)

    # -----------------------------------------------------------------------
    # 8. Save
    # -----------------------------------------------------------------------
    output_path = Path(args.output)
    if not output_path.is_absolute():
        output_path = (Path(__file__).parent / output_path).resolve()

    output_path.write_text(json.dumps(raw_output, indent=2, default=str, ensure_ascii=False), encoding="utf-8")
    results["Output saved to"] = str(output_path)

    emit_answers(results)

    # Write structured results alongside output
    results_path = output_path.with_suffix(".results.json")
    results_path.write_text(json.dumps(results, indent=2, ensure_ascii=False), encoding="utf-8")

    print(f"\n[OK] Raw output: {output_path}")
    print(f"[OK] Checklist:  {results_path}")
    print("\nNext: python models/omnishotcut/inspect_output.py --input sample_output.json")
    return 0


# ---------------------------------------------------------------------------
# Heuristics
# ---------------------------------------------------------------------------

def _detect_end_frame(output) -> str:
    """Heuristic: look for end_frame / end_frame_exclusive keys in raw output."""
    output_str = json.dumps(output, default=str).lower()
    if "end_frame_exclusive" in output_str:
        return "EXCLUSIVE (end_frame_exclusive found)"
    if "end_frame" in output_str:
        return "INCLUSIVE (end_frame found, no _exclusive variant)"
    return "UNKNOWN (no end_frame key found in raw output)"


def _detect_confidence(output) -> str:
    """Heuristic: look for confidence/score/prob keys."""
    output_str = json.dumps(output, default=str).lower()
    for key in ("confidence", "score", "probability", "prob"):
        if key in output_str:
            return f"YES (found '{key}' field)"
    return "UNKNOWN (no confidence-like key found)"


if __name__ == "__main__":
    sys.exit(main())
