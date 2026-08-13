"""Canonical Scene and SceneEvidence assembly.

Boundary semantics: a selected boundary closes the preceding Scene. Therefore
that Scene owns the boundary confidence, scene_score, and continuity evidence.
The terminal Scene has no following boundary, so its score/evidence are null.
"""

import uuid

from schemas.scene import Scene as SceneSchema
from schemas.scene import SceneEvidence as SceneEvidenceSchema


def _new_id() -> str:
    return uuid.uuid4().hex


def assemble_scenes(
    *,
    video_id: str,
    shots: list[dict],
    selected_boundaries: list[dict],
) -> tuple[list[dict], list[dict]]:
    """Build validated, contiguous Scene and evidence dictionaries."""
    if not shots:
        return [], []

    boundary_by_index = {
        int(boundary["boundary_index"]): boundary for boundary in selected_boundaries
    }
    ordered_boundary_indexes = sorted(boundary_by_index)
    scenes: list[dict] = []
    evidence: list[dict] = []
    first_shot_index = 0

    for scene_index, boundary_index in enumerate(ordered_boundary_indexes):
        if boundary_index < first_shot_index or boundary_index >= len(shots) - 1:
            raise ValueError(f"Invalid selected boundary index: {boundary_index}")

        scene_shots = shots[first_shot_index : boundary_index + 1]
        boundary = boundary_by_index[boundary_index]
        scene_id = _new_id()
        score = float(boundary["scene_score"])
        scene = SceneSchema(
            scene_id=scene_id,
            video_id=video_id,
            index=scene_index,
            start_ms=int(scene_shots[0]["start_ms"]),
            end_ms=int(scene_shots[-1]["end_ms"]),
            shot_ids=[str(shot["shot_id"]) for shot in scene_shots],
            boundary_confidence=score,
            scene_score=score,
        ).model_dump()
        scenes.append(scene)

        next_shot = shots[boundary_index + 1]
        location_value = boundary.get("location_change")
        character_value = boundary.get("character_group_change")
        location_change = float(location_value) / 100.0 if location_value is not None else None
        character_change = float(character_value) / 100.0 if character_value is not None else None
        item = SceneEvidenceSchema(
            scene_id=scene_id,
            visual_continuity=None,
            character_continuity=(
                round(1.0 - character_change, 4) if character_change is not None else None
            ),
            location_continuity=(
                round(1.0 - location_change, 4) if location_change is not None else None
            ),
            subtitle_continuity=boundary.get("subtitle_continuity"),
            audio_continuity=None,
            temporal_gap_ms=max(
                0,
                int(next_shot["start_ms"]) - int(scene_shots[-1]["end_ms"]),
            ),
        ).model_dump()
        evidence.append(item)
        first_shot_index = boundary_index + 1

    terminal_shots = shots[first_shot_index:]
    terminal_scene = SceneSchema(
        scene_id=_new_id(),
        video_id=video_id,
        index=len(scenes),
        start_ms=int(terminal_shots[0]["start_ms"]),
        end_ms=int(terminal_shots[-1]["end_ms"]),
        shot_ids=[str(shot["shot_id"]) for shot in terminal_shots],
        boundary_confidence=None,
        scene_score=None,
    ).model_dump()
    scenes.append(terminal_scene)

    _validate_scene_partition(shots, scenes)
    return scenes, evidence


def _validate_scene_partition(shots: list[dict], scenes: list[dict]) -> None:
    """Reject gaps, overlaps, missing shots, and duplicated shots."""
    expected_ids = [str(shot["shot_id"]) for shot in shots]
    actual_ids = [shot_id for scene in scenes for shot_id in scene["shot_ids"]]
    if actual_ids != expected_ids:
        raise ValueError("Scene shot_ids do not form the original ordered shot sequence")
    for previous, current in zip(scenes, scenes[1:], strict=False):
        if previous["end_ms"] > current["start_ms"]:
            raise ValueError("Scenes overlap in time")
