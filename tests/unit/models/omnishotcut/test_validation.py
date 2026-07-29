"""Unit tests for OmniShotCut shot validation."""

import pytest
from models.omnishotcut.validation import validate_shot_output, validate_shot_list


class TestValidateShotOutput:
    def test_valid_output(self):
        result = validate_shot_output({
            "video_id": "v1",
            "model": {"name": "omnishotcut", "version": "0.1.0"},
            "shots": [
                {"shot_id": "shot_000001", "video_id": "v1", "index": 0,
                 "start_frame": 0, "end_frame_exclusive": 457,
                 "start_ms": 0, "end_ms": 15233},
                {"shot_id": "shot_000002", "video_id": "v1", "index": 1,
                 "start_frame": 457, "end_frame_exclusive": 872,
                 "start_ms": 15233, "end_ms": 29033},
            ],
        })
        assert result["valid"] is True
        assert len(result["errors"]) == 0
        assert result["shot_count"] == 2

    def test_missing_shots_key(self):
        result = validate_shot_output({"video_id": "v1"})
        # Missing shots key → defaults to empty list → valid with warnings
        assert result["shot_count"] == 0

    def test_empty_shots(self):
        result = validate_shot_output({
            "video_id": "v1",
            "model": {"name": "omnishotcut", "version": "0.1.0"},
            "shots": [],
        })
        assert result["valid"] is True  # empty is not invalid, just has warnings
        assert len(result["warnings"]) >= 1

    def test_end_before_start(self):
        result = validate_shot_output({
            "video_id": "v1",
            "model": {"name": "omnishotcut", "version": "0.1.0"},
            "shots": [
                {"shot_id": "s1", "video_id": "v1", "index": 0,
                 "start_frame": 100, "end_frame_exclusive": 50,
                 "start_ms": 3000, "end_ms": 1500},
            ],
        })
        assert result["valid"] is False

    def test_gap_warning(self):
        result = validate_shot_output({
            "video_id": "v1",
            "model": {"name": "omnishotcut", "version": "0.1.0"},
            "shots": [
                {"shot_id": "s1", "video_id": "v1", "index": 0,
                 "start_frame": 0, "end_frame_exclusive": 100,
                 "start_ms": 0, "end_ms": 3000},
                {"shot_id": "s2", "video_id": "v1", "index": 1,
                 "start_frame": 100, "end_frame_exclusive": 200,
                 "start_ms": 5000, "end_ms": 6000},  # gap: end 3000 → start 5000
            ],
        })
        assert any("gap" in w.lower() or "not follow" in w.lower()
                   for w in result["warnings"])

    def test_forbidden_action_score(self):
        result = validate_shot_output({
            "video_id": "v1",
            "model": {"name": "omnishotcut", "version": "0.1.0"},
            "shots": [
                {"shot_id": "s1", "video_id": "v1", "index": 0,
                 "start_frame": 0, "end_frame_exclusive": 100,
                 "start_ms": 0, "end_ms": 3000,
                 "action_score": 0.5},  # FORBIDDEN
            ],
        })
        assert result["valid"] is False
        assert any("action_score" in e for e in result["errors"])

    def test_forbidden_plot_score(self):
        result = validate_shot_output({
            "video_id": "v1",
            "model": {"name": "omnishotcut", "version": "0.1.0"},
            "shots": [
                {"shot_id": "s1", "video_id": "v1", "index": 0,
                 "start_frame": 0, "end_frame_exclusive": 100,
                 "start_ms": 0, "end_ms": 3000,
                 "plot_score": 0.3},
            ],
        })
        assert result["valid"] is False

    def test_confidence_range(self):
        result = validate_shot_output({
            "video_id": "v1",
            "model": {"name": "omnishotcut", "version": "0.1.0"},
            "shots": [
                {"shot_id": "s1", "video_id": "v1", "index": 0,
                 "start_frame": 0, "end_frame_exclusive": 100,
                 "start_ms": 0, "end_ms": 3000, "confidence": 0.94},
            ],
        })
        assert result["valid"] is True

    def test_single_shot(self):
        result = validate_shot_output({
            "video_id": "v1",
            "model": {"name": "omnishotcut", "version": "0.1.0"},
            "shots": [
                {"shot_id": "s1", "video_id": "v1", "index": 0,
                 "start_frame": 0, "end_frame_exclusive": 2729,
                 "start_ms": 0, "end_ms": 90966},
            ],
        })
        assert result["valid"] is True
        assert result["shot_count"] == 1


class TestValidateShotList:
    def test_valid_list(self):
        result = validate_shot_list([
            {"shot_id": "s1", "video_id": "v1", "index": 0,
             "start_frame": 0, "end_frame_exclusive": 100,
             "start_ms": 0, "end_ms": 3000},
        ])
        assert result["valid"] is True
