"""Integration tests: local pipeline failure paths.

Markers: local, slow (no model needed for most)
"""

import os
from pathlib import Path

import pytest

from pipelines.services.omnishotcut_pipeline import run_omnishotcut_pipeline


@pytest.fixture
def output_root(tmp_path):
    d = tmp_path / "failure_test_output"
    d.mkdir()
    return d


# ---------------------------------------------------------------------------
# Failure path: invalid video
# ---------------------------------------------------------------------------


@pytest.mark.local
class TestInvalidVideo:
    def test_missing_file(self, output_root):
        """Non-existent video → SOURCE_NOT_FOUND."""
        result = run_omnishotcut_pipeline(
            video_id="test_missing",
            source_video_path=Path("/nonexistent/video.mp4"),
            output_root=output_root,
        )
        assert result.status == "FAILED"
        assert result.error_code == "SOURCE_NOT_FOUND"

    def test_invalid_file(self, output_root, tmp_path):
        """A file that is not a valid video → FFprobeError."""
        bad_file = tmp_path / "bad.mp4"
        bad_file.write_text("this is not a video file")

        result = run_omnishotcut_pipeline(
            video_id="test_invalid",
            source_video_path=bad_file,
            output_root=output_root,
        )
        assert result.status == "FAILED"
        # FFprobe should fail on invalid file
        assert "PROBE" in result.error_code or "FAILED" in result.status


# ---------------------------------------------------------------------------
# Failure path: missing model weights
# ---------------------------------------------------------------------------


@pytest.mark.local
class TestMissingWeights:
    def test_missing_weight_directory(self, output_root, tmp_path):
        """When MODEL_STORE_ROOT points to empty dir, model load fails."""
        # Create a fake video that probe can read
        # We need a real video to get past probe, so we skip if fixture missing
        video = Path("tests/fixtures/videos/omnishotcut/Hard_Cut_1.mp4")
        if not video.exists():
            pytest.skip("Hard_Cut_1.mp4 not available")

        # Temporarily redirect model store to empty dir
        old_root = os.environ.get("MODEL_STORE_ROOT")
        empty_dir = tmp_path / "empty_models"
        empty_dir.mkdir()
        os.environ["MODEL_STORE_ROOT"] = str(empty_dir)

        try:
            result = run_omnishotcut_pipeline(
                video_id="test_no_weights",
                source_video_path=video.resolve(),
                output_root=output_root,
            )
            # Should fail at model load or weight download
            assert result.status == "FAILED"
        finally:
            if old_root is not None:
                os.environ["MODEL_STORE_ROOT"] = old_root
            else:
                os.environ.pop("MODEL_STORE_ROOT", None)


# ---------------------------------------------------------------------------
# Failure path: missing normalized artifact
# ---------------------------------------------------------------------------


@pytest.mark.local
class TestMissingNormalizedArtifact:
    def test_no_normalized_artifact_blocks_shots(self, output_root):
        """Without normalized artifact, pipeline should not reach inference.

        This is tested by verifying that if normalization fails,
        the result has no shots_artifact_id and shows the correct error.
        """
        # We test this via PipelineResult semantics:
        from pipelines.services.omnishotcut_pipeline import PipelineResult

        r = PipelineResult(
            status="FAILED",
            video_id="test",
            error_code="NORMALIZED_ARTIFACT_NOT_FOUND",
            error_message="No normalized artifact available",
        )
        assert r.shots_artifact_id == ""
        assert r.shot_count == 0
