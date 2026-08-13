from apps.api.services.cache_service import canonical_cache_key, hash_json
from apps.api.services.workflow_service import (
    _remap_cached_keyframes,
    _remap_cached_subtitle_continuity,
    _remap_cached_vision_scores,
    _shot_timeline,
    _subtitle_content,
)
from schemas.task import AnalysisTaskRequest


def test_cache_key_is_canonical_and_input_sensitive():
    kwargs = {
        "stage": "shot.detect",
        "model_name": "ffmpeg_scene",
        "model_version": "1.0.0",
        "inputs": {"video_id": "video-a", "sha256": "abc"},
        "parameters": {"threshold": 0.1, "nested": {"b": 2, "a": 1}},
        "implementation": "contract-v1",
    }
    reordered = {
        **kwargs,
        "inputs": {"sha256": "abc", "video_id": "video-a"},
        "parameters": {"nested": {"a": 1, "b": 2}, "threshold": 0.1},
    }
    assert canonical_cache_key(**kwargs) == canonical_cache_key(**reordered)
    assert canonical_cache_key(**kwargs) != canonical_cache_key(
        **{**kwargs, "inputs": {"video_id": "video-a", "sha256": "changed"}}
    )


def test_task_force_recompute_is_validated_and_deduplicated():
    request = AnalysisTaskRequest(force_recompute=["vision", "vision", "asr"])
    assert request.force_recompute == ["vision", "asr"]


def test_task_independent_content_fingerprints_ignore_ids():
    first = [
        {"shot_id": "old", "start_ms": 0, "end_ms": 1000},
        {"shot_id": "old-2", "start_ms": 1000, "end_ms": 2000},
    ]
    second = [
        {"shot_id": "new", "start_ms": 0, "end_ms": 1000},
        {"shot_id": "new-2", "start_ms": 1000, "end_ms": 2000},
    ]
    assert hash_json(_shot_timeline(first)) == hash_json(_shot_timeline(second))

    old_subtitle = [{"subtitle_id": "old", "start_ms": 0, "end_ms": 500, "text": "hi"}]
    new_subtitle = [{"subtitle_id": "new", "start_ms": 0, "end_ms": 500, "text": "hi"}]
    assert _subtitle_content(old_subtitle) == _subtitle_content(new_subtitle)


def test_cached_json_outputs_remap_to_current_shot_ids():
    current = [
        {"shot_id": "new-a", "start_ms": 0, "end_ms": 1000},
        {"shot_id": "new-b", "start_ms": 1000, "end_ms": 2000},
    ]
    cached = [
        {"shot_id": "old-a", "start_ms": 0, "end_ms": 1000},
        {"shot_id": "old-b", "start_ms": 1000, "end_ms": 2000},
    ]
    vision = _remap_cached_vision_scores(
        current,
        cached,
        [{"shot_id": "old-a", "location_change": 50, "character_group_change": 20}],
    )
    assert vision is not None and vision[0]["shot_id"] == "new-a"

    continuity = _remap_cached_subtitle_continuity(
        current,
        cached,
        {"boundaries": [{"boundary_index": 0, "shot_id": "old-a", "timestamp_ms": 999}]},
    )
    assert continuity is not None
    assert continuity["boundaries"][0]["shot_id"] == "new-a"
    assert continuity["boundaries"][0]["timestamp_ms"] == 1000

    keyframes = _remap_cached_keyframes(
        current,
        {
            "shots": [
                {"shot_id": "old-a", "start_ms": 0, "end_ms": 1000, "samples": []},
                {"shot_id": "old-b", "start_ms": 1000, "end_ms": 2000, "samples": []},
            ]
        },
    )
    assert keyframes is not None
    assert [item["shot_id"] for item in keyframes["shots"]] == ["new-a", "new-b"]


def test_cache_remap_rejects_changed_timeline():
    current = [{"shot_id": "new", "start_ms": 0, "end_ms": 1000}]
    cached = [{"shot_id": "old", "start_ms": 0, "end_ms": 999}]
    assert _remap_cached_keyframes(current, {"shots": cached}) is None
