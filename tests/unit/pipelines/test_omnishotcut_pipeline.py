"""Unit tests for OmniShotCut pipeline service — no real model/ffmpeg."""

import hashlib
import tempfile
from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest

from pipelines.services.omnishotcut_pipeline import (
    PipelineResult,
    _new_id,
    _sha256_file,
    run_omnishotcut_pipeline,
)


class TestPipelineResult:
    def test_default_result_is_failed(self):
        r = PipelineResult(status="FAILED", video_id="v1")
        assert r.status == "FAILED"
        assert r.shot_count == 0
        assert r.runtime_ms == 0
        assert r.warnings == []

    def test_success_result(self):
        r = PipelineResult(
            status="SUCCEEDED",
            video_id="v1",
            shot_count=5,
            runtime_ms=1234,
            normalized_sha256="abc123",
        )
        assert r.status == "SUCCEEDED"
        assert r.shot_count == 5
        assert r.runtime_ms == 1234


class TestHelpers:
    def test_new_id_unique(self):
        ids = {_new_id() for _ in range(100)}
        assert len(ids) == 100

    def test_new_id_length(self):
        assert len(_new_id()) == 16

    def test_sha256_file(self, tmp_path):
        f = tmp_path / "test.txt"
        f.write_bytes(b"hello world")
        expected = hashlib.sha256(b"hello world").hexdigest()
        assert _sha256_file(f) == expected


class TestPipelineValidation:
    def test_missing_source_file(self, tmp_path):
        """Pipeline fails gracefully when source video doesn't exist."""
        result = run_omnishotcut_pipeline(
            video_id="test_v1",
            source_video_path=tmp_path / "nonexistent.mp4",
            output_root=tmp_path / "output",
        )
        assert result.status == "FAILED"
        assert result.error_code == "SOURCE_NOT_FOUND"

    def test_source_artifact_id_passed(self, tmp_path):
        """source_artifact_id is preserved in result."""
        # Test will fail at probe step (no real video), but checks ID passing
        fake_video = tmp_path / "fake.mp4"
        fake_video.write_bytes(b"not a real video")
        result = run_omnishotcut_pipeline(
            video_id="test_v1",
            source_video_path=fake_video,
            source_artifact_id="custom_artifact_001",
            output_root=tmp_path / "output",
        )
        assert result.source_artifact_id == "custom_artifact_001"

    def test_no_real_model_needed_for_basic_tests(self):
        """Basic PipelineResult creation and fields work without any model."""
        r = PipelineResult(
            status="SUCCEEDED",
            video_id="v_test",
            source_artifact_id="s_001",
            normalized_artifact_id="n_001",
            shots_artifact_id="sh_001",
            normalized_artifact_uri="/tmp/norm.mp4",
            shots_artifact_uri="/tmp/shots.json",
            shot_count=10,
            runtime_ms=5000,
        )
        assert r.source_artifact_id == "s_001"
        assert r.normalized_artifact_id == "n_001"
        assert r.shots_artifact_id == "sh_001"
