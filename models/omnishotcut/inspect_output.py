#!/usr/bin/env python3
"""
Inspect OmniShotCut raw output and map to project Shot Schema.

Reads the raw model output (sample_output.json), diagnoses its
structure, and prints a detailed report covering:

  - Raw output shape / type / keys
  - Time unit detection (ms? seconds? frames?)
  - End-frame convention (inclusive or exclusive)
  - Confidence field detection
  - How to map raw fields → schemas/shot.py

Usage:
  python models/omnishotcut/inspect_output.py --input sample_output.json

The goal is to answer the questions listed in the OmniShotCut README
before writing the Adapter.
"""

import argparse
import json
import sys
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT))


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Inspect OmniShotCut raw output against project Schema."
    )
    parser.add_argument(
        "--input",
        default="sample_output.json",
        help="Path to raw model output JSON (default: sample_output.json)",
    )
    args = parser.parse_args()

    input_path = Path(args.input)
    if not input_path.is_absolute():
        input_path = (Path(__file__).parent / input_path).resolve()

    if not input_path.is_file():
        print(f"[FAIL] File not found: {input_path}")
        return 1

    raw = json.loads(input_path.read_text(encoding="utf-8"))

    print("=" * 60)
    print("OmniShotCut — Raw Output Inspection")
    print("=" * 60)

    # ------------------------------------------------------------------
    # 1. Structure
    # ------------------------------------------------------------------
    print("\n## 1. Structure\n")
    print(f"  Type:         {type(raw).__name__}")
    if isinstance(raw, dict):
        print(f"  Keys:         {', '.join(sorted(raw.keys()))}")
        for k, v in raw.items():
            vtype = type(v).__name__
            if isinstance(v, list):
                print(f"    {k}: list[{len(v)} items]")
                if v:
                    print(f"      first item type:  {type(v[0]).__name__}")
                    if isinstance(v[0], dict):
                        print(f"      first item keys:  {', '.join(sorted(v[0].keys()))}")
            elif isinstance(v, dict):
                print(f"    {k}: dict[{', '.join(sorted(v.keys()))}]")
            else:
                print(f"    {k}: {vtype} = {_truncate(v)}")
    elif isinstance(raw, list):
        print(f"  Length:       {len(raw)}")
        if raw:
            print(f"  First item:   {type(raw[0]).__name__}")
            if isinstance(raw[0], dict):
                print(f"  Item keys:    {', '.join(sorted(raw[0].keys()))}")

    # ------------------------------------------------------------------
    # 2. Time unit detection
    # ------------------------------------------------------------------
    print("\n## 2. Time Unit\n")

    shots = _extract_shot_list(raw)
    if not shots:
        print("  [WARN] Could not locate shot/segment list in output.")
    else:
        time_keys = _find_time_keys(shots[0])
        print(f"  Time-related keys in first item: {time_keys}")

        for tk in time_keys:
            sample_values = _sample_values(shots, tk, n=5)
            print(f"  sample {tk}: {sample_values}")

        unit = _guess_time_unit(shots, time_keys)
        print(f"\n  **Guessed unit: {unit}**")

    # ------------------------------------------------------------------
    # 3. End-frame convention
    # ------------------------------------------------------------------
    print("\n## 3. End-Frame Convention\n")

    end_keys = [k for k in _all_keys(raw) if "end" in k.lower() and "frame" in k.lower()]
    print(f"  End-frame keys found: {end_keys if end_keys else 'NONE'}")

    raw_str = json.dumps(raw, default=str).lower()
    if "end_frame_exclusive" in raw_str:
        print("  Convention: EXCLUSIVE (end_frame_exclusive present)")
        print("  MAPPING: use as-is → schemas/shot.py end_frame_exclusive")
    elif "end_frame" in raw_str:
        print("  Convention: INCLUSIVE (end_frame found)")
        print("  MAPPING: end_frame_exclusive = raw_end_frame + 1")
    else:
        print("  Convention: UNKNOWN — manual review required")

    # ------------------------------------------------------------------
    # 4. Confidence
    # ------------------------------------------------------------------
    print("\n## 4. Confidence\n")

    conf_keys = [k for k in _all_keys(raw) if any(
        kw in k.lower() for kw in ("conf", "score", "prob", "certain")
    )]
    if conf_keys:
        print(f"  Confidence-like keys: {conf_keys}")
        if shots:
            samples = _sample_values(shots, conf_keys[0], n=5)
            print(f"  sample {conf_keys[0]}: {samples}")
            # Check range
            vals = [s.get(conf_keys[0]) for s in shots if conf_keys[0] in s]
            if vals:
                min_v, max_v = min(vals), max(vals)
                print(f"  Range: [{min_v}, {max_v}]")
                if all(isinstance(v, (int, float)) for v in vals if v is not None):
                    in_range = all(0 <= v <= 1 for v in vals if v is not None)
                    if in_range:
                        print("  Range check: [0,1] ✓")
                    else:
                        print("  Range check: OUTSIDE [0,1] — may need normalization")
    else:
        print("  [WARN] No confidence-like key found.")
        print("  Adapter may set confidence=None or compute from model internals.")

    # ------------------------------------------------------------------
    # 5. Target Schema mapping table
    # ------------------------------------------------------------------
    print("\n## 5. Schema Mapping\n")
    print("  Target: schemas/shot.py Shot")
    print(f"  {':<30} : raw source", "shot_id")
    print(f"  {':<30} : raw source", "video_id (from input context)")
    print(f"  {':<30} : raw source", "index")
    print(f"  {':<30} : raw source", "start_ms")
    print(f"  {':<30} : raw source", "end_ms")
    print(f"  {':<30} : raw source", "start_frame")
    print(f"  {':<30} : raw source", "end_frame_exclusive")
    print(f"  {':<30} : raw source", "boundary_type")
    print(f"  {':<30} : raw source", "confidence")

    print(f"\n  Fill in the raw source column above based on inspection.")

    # ------------------------------------------------------------------
    # 6. Any forbidden keys?
    # ------------------------------------------------------------------
    print("\n## 6. Forbidden Fields\n")
    forbidden = ["action_score", "plot_score"]
    for fk in forbidden:
        if fk in raw_str:
            print(f"  [WARN] '{fk}' found in output — must be stripped by Adapter")
    if not any(fk in raw_str for fk in forbidden):
        print("  No forbidden fields detected.")

    print("\n" + "=" * 60)
    print("Inspection complete.\n")
    print("Next steps:")
    print("  1. Fill in the mapping table above")
    print("  2. Write adapter.py using the raw→Schema mapping")
    print("  3. Run tests/ to validate Schema conversion")
    return 0


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _extract_shot_list(raw: Any) -> list[dict] | None:
    """Try to find the shot/segment list in the raw output."""
    if isinstance(raw, list):
        return raw
    if isinstance(raw, dict):
        for key in ("shots", "segments", "boundaries", "scenes", "data", "results", "predictions"):
            if key in raw and isinstance(raw[key], list):
                return raw[key]
    return None


def _all_keys(obj: Any, prefix: str = "") -> list[str]:
    """Recursively collect all dict keys from any depth."""
    keys: list[str] = []
    if isinstance(obj, dict):
        for k, v in obj.items():
            full = f"{prefix}.{k}" if prefix else k
            keys.append(full)
            keys.extend(_all_keys(v, full))
    elif isinstance(obj, list):
        for i, item in enumerate(obj):
            keys.extend(_all_keys(item, f"{prefix}[{i}]"))
    return keys


def _find_time_keys(item: dict) -> list[str]:
    """Find keys in a dict that look like time fields."""
    time_keywords = ("time", "ms", "timestamp", "start", "end", "frame", "second", "sec")
    return [k for k in item if any(kw in k.lower() for kw in time_keywords)]


def _guess_time_unit(shots: list[dict], time_keys: list[str]) -> str:
    """Guess whether values are in ms, seconds, or frames."""
    if not shots or not time_keys:
        return "UNKNOWN"

    for tk in time_keys:
        vals = [s.get(tk) for s in shots if tk in s and s.get(tk) is not None]
        if not vals:
            continue
        avg = sum(vals) / len(vals)
        if avg < 10:
            return f"SECONDS (avg {tk} = {avg:.3f})"
        if avg > 1000:
            return f"MILLISECONDS (avg {tk} = {avg:.0f})"
        if 10 <= avg <= 1000:
            return f"UNCERTAIN — could be frames or small ms. avg {tk} = {avg:.1f}"

    return "UNKNOWN"


def _sample_values(items: list[dict], key: str, n: int = 5) -> str:
    """Show first n values for a key across items."""
    vals = []
    for item in items[:n]:
        if key in item:
            vals.append(item[key])
    return str(vals) if vals else "(key not found)"


def _truncate(value: Any, n: int = 80) -> str:
    s = str(value)
    return s if len(s) <= n else s[:n] + "..."



if __name__ == "__main__":
    sys.exit(main())
