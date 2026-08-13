import json

import pytest
from PIL import Image

from models.doubao_vision.adapter import DoubaoVisionAdapter
from models.doubao_vision.providers.seedvision import SeedVisionAPIError


class _VisionProvider:
    def send(self, messages):
        shot_id = messages[1]["content"][0]["text"].split("Required Shot IDs: ", 1)[1]
        return {
            "data": {
                "scores": [
                    {
                        "shot_id": shot_id,
                        "location_change": 80,
                        "character_group_change": 20,
                    }
                ]
            }
        }


class _RetryingVisionProvider(_VisionProvider):
    def __init__(self):
        self.calls = 0

    def send(self, messages):
        self.calls += 1
        if self.calls == 1:
            return {"data": {"scores": []}}
        return super().send(messages)


class _FormattedIdVisionProvider(_VisionProvider):
    def send(self, messages):
        response = super().send(messages)
        response["data"]["scores"][0]["shot_id"] = "model-formatted-id"
        response["data"]["scores"][0]["location_change"] = "80"
        return response


def test_vision_provider_account_error_is_not_retryable() -> None:
    error = SeedVisionAPIError("AccountOverdueError", retryable=False)

    assert not error.retryable
    with pytest.raises(SeedVisionAPIError):
        raise error


def test_vision_adapter_resolves_keyframes_from_summary_artifact(tmp_path) -> None:
    shot_a = "a" * 32
    shot_b = "b" * 32
    end_image = tmp_path / "shared-end.jpg"
    start_image = tmp_path / "shared-start.jpg"
    Image.new("RGB", (16, 16), "red").save(end_image)
    Image.new("RGB", (16, 16), "blue").save(start_image)
    shots_path = tmp_path / "shots.json"
    shots_path.write_text(
        json.dumps(
            {
                "shots": [
                    {"shot_id": shot_a, "index": 0},
                    {"shot_id": shot_b, "index": 1},
                ]
            }
        ),
        encoding="utf-8",
    )
    keyframes_path = tmp_path / "keyframes.json"
    keyframes_path.write_text(
        json.dumps(
            {
                "shots": [
                    {
                        "shot_id": shot_a,
                        "samples": [
                            {
                                "position_num": 3,
                                "position_den": 4,
                                "uri": str(end_image),
                            }
                        ],
                    },
                    {
                        "shot_id": shot_b,
                        "samples": [
                            {
                                "position_num": 1,
                                "position_den": 4,
                                "uri": str(start_image),
                            }
                        ],
                    },
                ]
            }
        ),
        encoding="utf-8",
    )
    adapter = DoubaoVisionAdapter()
    adapter._provider = _VisionProvider()
    adapter._loaded = True

    output = adapter.predict(
        {
            "schema_version": "1.0",
            "task_id": "c" * 32,
            "video_id": "d" * 32,
            "input": {
                "shots_uri": str(shots_path),
                "keyframes_uri": str(keyframes_path),
            },
            "parameters": {"batch_size": 1},
        }
    )

    assert output["status"] == "SUCCEEDED"
    assert adapter._last_result["scores"][0]["shot_id"] == shot_a


def test_vision_adapter_retries_an_incomplete_boundary_response(tmp_path) -> None:
    shot_a = "a" * 32
    shot_b = "b" * 32
    images = []
    for name, colour in (("end.jpg", "red"), ("start.jpg", "blue")):
        path = tmp_path / name
        Image.new("RGB", (16, 16), colour).save(path)
        images.append(path)
    shots_path = tmp_path / "shots.json"
    shots_path.write_text(
        json.dumps({"shots": [{"shot_id": shot_a}, {"shot_id": shot_b}]}),
        encoding="utf-8",
    )
    keyframes_path = tmp_path / "keyframes.json"
    keyframes_path.write_text(
        json.dumps(
            {
                "shots": [
                    {
                        "shot_id": shot_a,
                        "samples": [{"position_num": 3, "position_den": 4, "uri": str(images[0])}],
                    },
                    {
                        "shot_id": shot_b,
                        "samples": [{"position_num": 1, "position_den": 4, "uri": str(images[1])}],
                    },
                ]
            }
        ),
        encoding="utf-8",
    )
    provider = _RetryingVisionProvider()
    adapter = DoubaoVisionAdapter()
    adapter._provider = provider
    adapter._loaded = True

    output = adapter.predict(
        {
            "task_id": "c" * 32,
            "video_id": "d" * 32,
            "input": {"shots_uri": str(shots_path), "keyframes_uri": str(keyframes_path)},
            "parameters": {"max_attempts": 2},
        }
    )

    assert output["status"] == "SUCCEEDED"
    assert provider.calls == 2


def test_vision_adapter_binds_single_response_to_trusted_boundary_id(tmp_path) -> None:
    shot_a = "a" * 32
    shot_b = "b" * 32
    end_image = tmp_path / "end.jpg"
    start_image = tmp_path / "start.jpg"
    Image.new("RGB", (16, 16), "red").save(end_image)
    Image.new("RGB", (16, 16), "blue").save(start_image)
    shots_path = tmp_path / "shots.json"
    shots_path.write_text(
        json.dumps({"shots": [{"shot_id": shot_a}, {"shot_id": shot_b}]}),
        encoding="utf-8",
    )
    keyframes_path = tmp_path / "keyframes.json"
    keyframes_path.write_text(
        json.dumps(
            {
                "shots": [
                    {
                        "shot_id": shot_a,
                        "samples": [
                            {"position_num": 3, "position_den": 4, "uri": str(end_image)}
                        ],
                    },
                    {
                        "shot_id": shot_b,
                        "samples": [
                            {"position_num": 1, "position_den": 4, "uri": str(start_image)}
                        ],
                    },
                ]
            }
        ),
        encoding="utf-8",
    )
    adapter = DoubaoVisionAdapter()
    adapter._provider = _FormattedIdVisionProvider()
    adapter._loaded = True

    output = adapter.predict(
        {
            "task_id": "c" * 32,
            "video_id": "d" * 32,
            "input": {"shots_uri": str(shots_path), "keyframes_uri": str(keyframes_path)},
            "parameters": {"batch_size": 1},
        }
    )

    assert output["status"] == "SUCCEEDED"
    score = adapter._last_result["scores"][0]
    assert score["shot_id"] == shot_a
    assert score["location_change"] == 80.0
