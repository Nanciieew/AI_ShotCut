import json

from models.subtitle_semantic.adapter import (
    SubtitleSemanticAdapter,
    _build_local_intervals,
    _chunk_subtitles,
    _dynamic_global_limit,
    _map_candidates_to_shots,
)


class FakeProvider:
    def __init__(self, responses):
        self.responses = iter(responses)
        self.calls = 0

    def send(self, messages, **kwargs):  # noqa: ARG002
        self.calls += 1
        return {"data": next(self.responses), "telemetry": {"elapsed_ms": 1}}

    def health_check(self):
        return True


class MemoryStageCache:
    def __init__(self):
        self.data = {}

    @staticmethod
    def _key(stage, payload):
        return stage, json.dumps(payload, ensure_ascii=False, sort_keys=True)

    def get(self, stage, payload):
        return self.data.get(self._key(stage, payload))

    def put(self, stage, payload, data):
        self.data[self._key(stage, payload)] = data


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
            {
                "intervals": [
                    {
                        "interval_id": "i0",
                        "candidates": [{"timestamp_ms": 20_100, "reason": "new goal"}],
                    }
                ]
            },
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
    assert len(adapter._last_result["analysis"]["requests"]) == 4


def test_dynamic_global_limit_reduces_transition_density_for_longer_video() -> None:
    assert _dynamic_global_limit(3 * 60_000) == 4
    assert _dynamic_global_limit(10 * 60_000) == 5
    assert _dynamic_global_limit(60 * 60_000) == 10
    assert _dynamic_global_limit(180 * 60_000) == 10


def test_tiny_local_intervals_are_merged_before_requests() -> None:
    subtitles = [
        {"start_ms": 0, "end_ms": 1_000, "text": "a"},
        {"start_ms": 11_000, "end_ms": 12_000, "text": "substantial dialogue here"},
        {"start_ms": 13_000, "end_ms": 14_000, "text": "another dialogue line"},
        {"start_ms": 15_000, "end_ms": 16_000, "text": "third dialogue line"},
    ]
    intervals = _build_local_intervals(
        subtitles,
        [0, 10_000, 20_000],
        min_chars=20,
        min_segments=2,
    )
    assert len(intervals) == 1
    assert intervals[0]["start_ms"] == 0
    assert intervals[0]["end_ms"] == 20_000


def test_stage_cache_reuses_every_deepseek_phase_without_new_requests() -> None:
    responses = [
        {"summary": "setup and turn", "events": []},
        {"candidates": [{"timestamp_ms": 10_100, "reason": "turn"}]},
        {"intervals": [{"interval_id": "i0", "candidates": []}]},
        {"boundaries": [{"boundary_id": "b0", "subtitle_continuity": 0.2, "reason": "turn"}]},
    ]
    cache = MemoryStageCache()
    payload = {
        "task_id": "task",
        "video_id": "video",
        "input": {
            "subtitle_segments": [
                {"start_ms": 0, "end_ms": 9_000, "text": "setup dialogue"},
                {"start_ms": 10_000, "end_ms": 19_000, "text": "truth revealed"},
            ],
            "shots": [
                {"shot_id": "s0", "start_ms": 0, "end_ms": 10_000},
                {"shot_id": "s1", "start_ms": 10_000, "end_ms": 20_000},
            ],
        },
        "parameters": {},
    }
    first_provider = FakeProvider(responses)
    first = SubtitleSemanticAdapter(provider=first_provider, stage_cache=cache)
    assert first.predict(payload)["status"] == "SUCCEEDED"
    assert first_provider.calls == 4

    second_provider = FakeProvider([])
    second = SubtitleSemanticAdapter(provider=second_provider, stage_cache=cache)
    assert second.predict(payload)["status"] == "SUCCEEDED"
    assert second_provider.calls == 0
    assert second._last_result["analysis"]["stage_cache"]["hits"] == 4


def test_invalid_json_uses_short_repair_request_and_limits_reason() -> None:
    long_reason = "x" * 500

    class RepairProvider(FakeProvider):
        def send(self, messages, **kwargs):  # noqa: ARG002
            self.calls += 1
            value = next(self.responses)
            if value == "malformed":
                return {"data": {"raw_text": "{bad"}, "raw": "{bad"}
            return {"data": value, "telemetry": {"elapsed_ms": 1}}

    provider = RepairProvider(
        [
            "malformed",
            {"summary": "repaired", "events": []},
            {"candidates": [{"timestamp_ms": 10_100, "reason": long_reason}]},
            {"intervals": [{"interval_id": "i0", "candidates": []}]},
            {
                "boundaries": [
                    {
                        "boundary_id": "b0",
                        "subtitle_continuity": 0.2,
                        "reason": long_reason,
                    }
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
                    {"start_ms": 0, "end_ms": 9_000, "text": "setup dialogue"},
                    {"start_ms": 10_000, "end_ms": 19_000, "text": "truth revealed"},
                ],
                "shots": [
                    {"shot_id": "s0", "start_ms": 0, "end_ms": 10_000},
                    {"shot_id": "s1", "start_ms": 10_000, "end_ms": 20_000},
                ],
            },
            "parameters": {},
        }
    )
    assert output["status"] == "SUCCEEDED"
    assert provider.calls == 5
    assert len(adapter._last_result["boundaries"][0]["reason"]) == 160
    assert adapter._last_result["analysis"]["requests"][1]["stage"].endswith("json_repair")
