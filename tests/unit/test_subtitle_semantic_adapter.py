from models.subtitle_semantic.adapter import (
    SubtitleSemanticAdapter,
    _chunk_subtitles,
    _map_candidates_to_shots,
)


class FakeProvider:
    def __init__(self, responses):
        self.responses = iter(responses)

    def send(self, messages, **kwargs):  # noqa: ARG002
        return {"data": next(self.responses)}

    def health_check(self):
        return True


def test_chunking_preserves_order_and_integer_time_ranges() -> None:
    items = [
        {"start_ms": 0, "end_ms": 1_000, "text": "aaaa"},
        {"start_ms": 1_000, "end_ms": 2_000, "text": "bbbb"},
        {"start_ms": 2_000, "end_ms": 3_000, "text": "cccc"},
    ]

    chunks = _chunk_subtitles(items, max_chars=8, max_duration_ms=10_000)

    assert [(item["start_ms"], item["end_ms"]) for item in chunks] == [
        (0, 2_000),
        (2_000, 3_000),
    ]


def test_candidate_mapping_deduplicates_global_and_local_hits() -> None:
    shots = [
        {"shot_id": "s0", "start_ms": 0, "end_ms": 10_000},
        {"shot_id": "s1", "start_ms": 10_000, "end_ms": 20_000},
        {"shot_id": "s2", "start_ms": 20_000, "end_ms": 30_000},
    ]
    candidates = [
        {"timestamp_ms": 9_500, "source": "global"},
        {"timestamp_ms": 10_200, "source": "local"},
    ]

    mapped = _map_candidates_to_shots(
        candidates,
        shots,
        max_snap_ms=8_000,
        max_snap_shots=2,
    )

    assert mapped == [
        {
            "shot_id": "s0",
            "boundary_index": 0,
            "timestamp_ms": 10_000,
            "discovery_sources": ["global", "local"],
            "discovery_reasons": [],
        }
    ]


def test_adapter_discovers_hierarchically_then_uniformly_rescores() -> None:
    provider = FakeProvider(
        [
            {"summary": "setup then revelation", "events": []},
            {"candidates": [{"timestamp_ms": 10_100, "reason": "revelation"}]},
            {"candidates": []},
            {"candidates": [{"timestamp_ms": 20_100, "reason": "new goal"}]},
            {
                "boundaries": [
                    {"boundary_id": "b0", "subtitle_continuity": 0.1, "reason": "revelation"},
                    {"boundary_id": "b1", "subtitle_continuity": 0.4, "reason": "new goal"},
                ]
            },
        ]
    )
    adapter = SubtitleSemanticAdapter(provider=provider)
    output = adapter.predict(
        {
            "task_id": "task",
            "video_id": "video",
            "input": {
                "subtitle_segments": [
                    {"start_ms": 0, "end_ms": 9_000, "text": "setup"},
                    {"start_ms": 10_000, "end_ms": 19_000, "text": "truth revealed"},
                    {"start_ms": 20_000, "end_ms": 29_000, "text": "new goal"},
                ],
                "shots": [
                    {"shot_id": "s0", "start_ms": 0, "end_ms": 10_000},
                    {"shot_id": "s1", "start_ms": 10_000, "end_ms": 20_000},
                    {"shot_id": "s2", "start_ms": 20_000, "end_ms": 30_000},
                ],
            },
            "parameters": {},
        }
    )

    assert output["status"] == "SUCCEEDED"
    assert [item["subtitle_continuity"] for item in adapter._last_result["boundaries"]] == [
        0.1,
        0.4,
    ]
    assert adapter._last_result["boundaries"][0]["discovery_sources"] == ["global"]
