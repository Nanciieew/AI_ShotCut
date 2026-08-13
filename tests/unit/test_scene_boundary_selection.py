import pytest
from pydantic import ValidationError

from apps.api.services.scene_service import assemble_scenes
from apps.api.services.workflow_service import (
    _canonicalize_shots,
    _pipeline_requirements,
    _remap_cached_subtitle_continuity,
    _remap_cached_vision_scores,
    _score_weights,
    _select_boundaries,
    _weighted_change,
)
from schemas.task import AnalysisTaskRequest


def test_cached_vision_scores_remap_only_for_identical_timeline() -> None:
    current = [
        {"shot_id": "new-a", "start_ms": 0, "end_ms": 1000},
        {"shot_id": "new-b", "start_ms": 1000, "end_ms": 2000},
    ]
    cached = [
        {"shot_id": "old-a", "start_ms": 0, "end_ms": 1000},
        {"shot_id": "old-b", "start_ms": 1000, "end_ms": 2000},
    ]
    scores = [{"shot_id": "old-a", "location_change": 80, "character_group_change": 20}]

    remapped = _remap_cached_vision_scores(current, cached, scores)

    assert remapped is not None
    assert remapped[0]["shot_id"] == "new-a"
    assert (
        _remap_cached_vision_scores(
            current,
            [{**cached[0], "end_ms": 999}, cached[1]],
            scores,
        )
        is None
    )


def test_cached_subtitle_continuity_remaps_sparse_boundary_ids() -> None:
    current = [
        {"shot_id": "new-a", "start_ms": 0, "end_ms": 1000},
        {"shot_id": "new-b", "start_ms": 1000, "end_ms": 2000},
    ]
    cached = [
        {"shot_id": "old-a", "start_ms": 0, "end_ms": 1000},
        {"shot_id": "old-b", "start_ms": 1000, "end_ms": 2000},
    ]
    data = {
        "video_id": "video",
        "boundaries": [
            {
                "shot_id": "old-a",
                "boundary_index": 0,
                "timestamp_ms": 999,
                "subtitle_continuity": 0.2,
            }
        ],
    }

    remapped = _remap_cached_subtitle_continuity(current, cached, data)

    assert remapped is not None
    assert remapped["boundaries"][0]["shot_id"] == "new-a"
    assert remapped["boundaries"][0]["timestamp_ms"] == 1000


def test_only_modes_have_exact_coefficients() -> None:
    assert _score_weights("location_only", 8, 7, 6) == {
        "location": 1.0,
        "character": 0.0,
        "subtitle": 0.0,
    }
    assert _score_weights("character_only", 8, 7, 6) == {
        "location": 0.0,
        "character": 1.0,
        "subtitle": 0.0,
    }
    assert _score_weights("subtitle_only", 8, 7, 6) == {
        "location": 0.0,
        "character": 0.0,
        "subtitle": 1.0,
    }


def test_request_exposes_exactly_four_modes() -> None:
    field = AnalysisTaskRequest.model_json_schema()["properties"]["score_mode"]

    assert field["default"] == "location_only"
    assert field["enum"] == [
        "location_only",
        "character_only",
        "subtitle_only",
        "custom",
    ]


def test_custom_request_rejects_all_zero_weights() -> None:
    try:
        AnalysisTaskRequest(
            score_mode="custom",
            location_weight=0,
            character_weight=0,
            subtitle_weight=0,
        )
    except ValidationError:
        pass
    else:
        raise AssertionError("all-zero custom weights must be rejected")


def test_shot_ids_are_globally_unique_across_runs() -> None:
    first = _canonicalize_shots([{"shot_id": "shot_000001"}], "v1")
    second = _canonicalize_shots([{"shot_id": "shot_000001"}], "v1")

    assert len(first[0]["shot_id"]) == 32
    assert first[0]["shot_id"] != second[0]["shot_id"]
    assert first[0]["video_id"] == "v1"


def test_custom_weights_are_normalized_by_total() -> None:
    weights = _score_weights("custom", 10, 10)

    assert weights == {"location": 0.5, "character": 0.5, "subtitle": 0.0}
    assert sum(weights.values()) == 1.0


def test_custom_weights_preserve_ratio() -> None:
    weights = _score_weights("custom", 3, 1)

    assert weights == {"location": 0.75, "character": 0.25, "subtitle": 0.0}


def test_all_three_custom_weights_are_normalized() -> None:
    weights = _score_weights("custom", 2, 3, 5)

    assert weights == {"location": 0.2, "character": 0.3, "subtitle": 0.5}


def test_missing_required_evidence_is_rejected() -> None:
    with pytest.raises(ValueError, match="character, location"):
        _weighted_change(
            {"location": None, "character": None, "subtitle": 0.8},
            {"location": 0.4, "character": 0.3, "subtitle": 0.3},
        )


def test_pipeline_requirements_isolate_provider_branches() -> None:
    assert _pipeline_requirements(False, "location_only", 1, 1, 1)[1:] == (
        False,
        False,
    )
    assert _pipeline_requirements(True, "location_only", 1, 1, 1)[1:] == (
        True,
        False,
    )
    assert _pipeline_requirements(True, "character_only", 1, 1, 1)[1:] == (
        True,
        False,
    )
    assert _pipeline_requirements(True, "subtitle_only", 1, 1, 1)[1:] == (
        False,
        True,
    )
    assert _pipeline_requirements(True, "custom", 0, 3, 5)[1:] == (True, True)


def test_high_score_is_selected_before_nearby_earlier_low_score() -> None:
    boundaries = [
        {"timestamp_ms": 10_000, "scene_score": 0.05},
        {"timestamp_ms": 18_000, "scene_score": 0.95},
        {"timestamp_ms": 30_000, "scene_score": 0.70},
    ]

    selected = _select_boundaries(
        boundaries,
        min_distance_ms=12_000,
        target_count=1,
    )

    assert selected == [{"timestamp_ms": 18_000, "scene_score": 0.95}]


def test_selection_stops_at_target_count_and_returns_time_order() -> None:
    boundaries = [
        {"timestamp_ms": 30_000, "scene_score": 0.70},
        {"timestamp_ms": 10_000, "scene_score": 0.80},
        {"timestamp_ms": 50_000, "scene_score": 0.90},
    ]

    selected = _select_boundaries(
        boundaries,
        min_distance_ms=5_000,
        target_count=2,
    )

    assert selected == [
        {"timestamp_ms": 10_000, "scene_score": 0.80},
        {"timestamp_ms": 50_000, "scene_score": 0.90},
    ]


def test_scene_assembly_creates_uuid_ids_shot_partition_and_evidence() -> None:
    shots = [
        {"shot_id": "shot_a", "start_ms": 0, "end_ms": 1_000},
        {"shot_id": "shot_b", "start_ms": 1_000, "end_ms": 2_000},
        {"shot_id": "shot_c", "start_ms": 2_000, "end_ms": 3_000},
    ]
    selected = [
        {
            "boundary_index": 1,
            "timestamp_ms": 2_000,
            "scene_score": 0.8,
            "location_change": 75.0,
            "character_group_change": 20.0,
            "subtitle_continuity": 0.1,
        }
    ]

    scenes, evidence = assemble_scenes(
        video_id="a" * 32,
        shots=shots,
        selected_boundaries=selected,
    )

    assert len(scenes) == 2
    assert len(scenes[0]["scene_id"]) == 32
    assert scenes[0]["shot_ids"] == ["shot_a", "shot_b"]
    assert scenes[1]["shot_ids"] == ["shot_c"]
    assert scenes[1]["scene_score"] is None
    assert evidence == [
        {
            "scene_id": scenes[0]["scene_id"],
            "visual_continuity": None,
            "character_continuity": 0.8,
            "location_continuity": 0.25,
            "subtitle_continuity": 0.1,
            "audio_continuity": None,
            "temporal_gap_ms": 0,
        }
    ]
