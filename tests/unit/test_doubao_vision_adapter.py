import json

import pytest
from PIL import Image

from models.doubao_vision.adapter import DoubaoVisionAdapter
from models.doubao_vision.providers.seedvision import SeedVisionAPIError


class _DescriptorProvider:
    def __init__(self) -> None:
        self.calls: list[list[dict]] = []

    def send(self, messages):
        self.calls.append(messages)
        text = messages[1]["content"][0]["text"]
        shot_id = text.split("Describe Shot ID: ", 1)[1].splitlines()[0]
        index = {"a": 0, "b": 1, "c": 2}[shot_id[0]]
        if index < 2:
            location_match = None if index == 0 else "location_0001"
            character_match = None if index == 0 else "character_0001"
            place_type = "bedroom"
            character_description = "woman with long dark hair and a red robe"
        else:
            location_match = None
            character_match = None
            place_type = "street"
            character_description = "older man with grey beard and blue coat"
        return {
            "data": {
                "shot_id": shot_id,
                "location": {
                    "matched_location_id": location_match,
                    "environment": "indoor" if index < 2 else "outdoor",
                    "place_type": place_type,
                    "spatial_layout": ["bed at rear"] if index < 2 else ["wide road"],
                    "landmarks": ["red curtain"] if index < 2 else ["stone gate"],
                    "background_objects": ["table"] if index < 2 else ["cart"],
                    "architecture_style": "traditional_chinese",
                    "materials": ["wood"] if index < 2 else ["stone"],
                    "dominant_colors": ["red"] if index < 2 else ["grey"],
                    "lighting": "warm" if index < 2 else "daylight",
                    "time_of_day": "unknown" if index < 2 else "day",
                    "weather": "not_applicable" if index < 2 else "clear",
                    "confidence": 0.9,
                },
                "characters": [
                    {
                        "matched_character_id": character_match,
                        "stable_description": character_description,
                        "is_primary": True,
                        "visibility": 0.95,
                    }
                ],
                "quality": {"blurred": False, "occluded": False},
                "reason": "test evidence",
            }
        }


class _RetryingDescriptorProvider(_DescriptorProvider):
    def __init__(self) -> None:
        super().__init__()
        self.attempts = 0

    def send(self, messages):
        self.attempts += 1
        if self.attempts == 1:
            self.calls.append(messages)
            return {"data": {"invalid": True}}
        return super().send(messages)


def _input_artifacts(tmp_path, shot_ids):
    shots_path = tmp_path / "shots.json"
    shots_path.write_text(
        json.dumps(
            {"shots": [{"shot_id": shot_id, "index": i} for i, shot_id in enumerate(shot_ids)]}
        ),
        encoding="utf-8",
    )
    keyframe_shots = []
    for shot_index, shot_id in enumerate(shot_ids):
        samples = []
        for position_num, position_den in ((1, 4), (1, 2), (3, 4)):
            image_path = tmp_path / f"{shot_index}-{position_num}-{position_den}.jpg"
            Image.new("RGB", (16, 16), (shot_index * 50, position_num * 50, 20)).save(image_path)
            samples.append(
                {
                    "position_num": position_num,
                    "position_den": position_den,
                    "uri": str(image_path),
                }
            )
        keyframe_shots.append({"shot_id": shot_id, "samples": samples})
    keyframes_path = tmp_path / "keyframes.json"
    keyframes_path.write_text(json.dumps({"shots": keyframe_shots}), encoding="utf-8")
    return shots_path, keyframes_path


def _run_adapter(tmp_path, provider, shot_ids=None):
    shot_ids = shot_ids or ["a" * 32, "b" * 32, "c" * 32]
    shots_path, keyframes_path = _input_artifacts(tmp_path, shot_ids)
    adapter = DoubaoVisionAdapter()
    adapter._provider = provider
    adapter._loaded = True
    output = adapter.predict(
        {
            "schema_version": "1.0",
            "task_id": "d" * 32,
            "video_id": "e" * 32,
            "input": {"shots_uri": str(shots_path), "keyframes_uri": str(keyframes_path)},
            "parameters": {"max_attempts": 2},
        }
    )
    return adapter, output


def test_vision_provider_account_error_is_not_retryable() -> None:
    error = SeedVisionAPIError("AccountOverdueError", retryable=False)
    assert not error.retryable
    with pytest.raises(SeedVisionAPIError):
        raise error


def test_adapter_uses_three_frames_and_carries_task_registry(tmp_path) -> None:
    provider = _DescriptorProvider()
    adapter, output = _run_adapter(tmp_path, provider)

    assert output["status"] == "SUCCEEDED"
    assert len(provider.calls) == 3
    assert all(len(call[1]["content"]) == 4 for call in provider.calls)  # text + 3 images
    assert "location_0001" in provider.calls[1][1]["content"][0]["text"]
    assert "character_0001" in provider.calls[1][1]["content"][0]["text"]
    assert len(adapter._last_result["shot_descriptors"]) == 3


def test_adapter_reuses_identities_and_scores_real_replacement_high(tmp_path) -> None:
    adapter, output = _run_adapter(tmp_path, _DescriptorProvider())
    assert output["status"] == "SUCCEEDED"

    descriptors = adapter._last_result["shot_descriptors"]
    assert descriptors[0]["location"]["location_id"] == descriptors[1]["location"]["location_id"]
    assert (
        descriptors[0]["characters"][0]["character_id"]
        == descriptors[1]["characters"][0]["character_id"]
    )
    assert descriptors[2]["characters"][0]["first_shot_index"] == 2

    scores = adapter._last_result["scores"]
    assert scores[0]["location_change"] <= 25
    assert scores[0]["character_group_change"] == 0
    assert scores[1]["location_change"] > 60
    assert scores[1]["character_group_change"] == 100
    assert scores[1]["character_evidence"]["first_appearances"] == ["character_0002"]


def test_adapter_retries_invalid_shot_descriptor(tmp_path) -> None:
    provider = _RetryingDescriptorProvider()
    _, output = _run_adapter(tmp_path, provider, ["a" * 32, "b" * 32])
    assert output["status"] == "SUCCEEDED"
    assert provider.attempts == 3  # first shot retries once, second succeeds once
