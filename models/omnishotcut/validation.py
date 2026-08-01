"""Output validation for OmniShotCut → Shot Schema.

Validates that converted output conforms to:
  - schemas/shot.py Pydantic model
  - Project time/range conventions
  - No forbidden fields
"""

from schemas.shot import Shot


def validate_shot_output(shots_json: dict) -> dict:
    """Validate converted shot output against the Shot Schema.

    Args:
        shots_json: Dict with a "shots" key containing shot dicts.

    Returns:
        {
            "valid": bool,
            "shot_count": int,
            "errors": list[str],
            "warnings": list[str],
        }

    Raises:
        Does NOT raise — always returns a validation report dict.
    """
    report: dict = {
        "valid": True,
        "shot_count": 0,
        "errors": [],
        "warnings": [],
    }

    shots = shots_json.get("shots", [])
    if not isinstance(shots, list):
        report["valid"] = False
        report["errors"].append("'shots' key must contain a list")
        return report

    report["shot_count"] = len(shots)

    if len(shots) == 0:
        report["warnings"].append("No shots found in output")

    prev_end_ms = None
    for i, raw in enumerate(shots):
        try:
            shot = Shot.model_validate(raw)
        except Exception as e:
            report["valid"] = False
            report["errors"].append(f"Shot[{i}] failed Schema validation: {e}")
            continue

        # Check time continuity: consecutive shots should have no gaps
        if prev_end_ms is not None and shot.start_ms != prev_end_ms:
            report["warnings"].append(
                f"Shot[{i}] (start={shot.start_ms}ms) does not "
                f"follow previous end ({prev_end_ms}ms) — gap or overlap"
            )
        prev_end_ms = shot.end_ms

        # Range sanity
        if shot.end_ms <= shot.start_ms:
            report["valid"] = False
            report["errors"].append(
                f"Shot[{i}]: end_ms ({shot.end_ms}) <= start_ms ({shot.start_ms})"
            )

        if shot.end_frame_exclusive is not None and shot.start_frame is not None:
            if shot.end_frame_exclusive <= shot.start_frame:
                report["valid"] = False
                report["errors"].append(f"Shot[{i}]: end_frame_exclusive <= start_frame")

        # Check forbidden fields
        forbidden = ["action_score", "plot_score", "action_evidence", "plot_evidence"]
        for fk in forbidden:
            if fk in raw:
                report["valid"] = False
                report["errors"].append(f"Shot[{i}] contains forbidden field: {fk}")

    return report


def validate_shot_list(shots: list[dict]) -> dict:
    """Shorthand: validate a list of shot dicts directly."""
    return validate_shot_output({"shots": shots, "video_id": "unknown"})
