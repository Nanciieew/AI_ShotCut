"""Integration tests: full local pipeline (requires ffmpeg + OmniShotCut model).

Markers: local, model, slow
"""

from pathlib import Path

import pytest

from pipelines.services.omnishotcut_pipeline import run_omnishotcut_pipeline

# ---------------------------------------------------------------------------
# Test configuration
# ---------------------------------------------------------------------------


@pytest.fixture
def hard_cut_video():
    candidates = [
        Path("tests/fixtures/videos/omnishotcut/Hard_Cut_1.mp4"),
        Path("data/test_videos/Hard_Cut_1.mp4"),
    ]
    for p in candidates:
        if p.exists():
            return p.resolve()
    pytest.skip("Hard_Cut_1.mp4 not found")


@pytest.fixture
def output_root(tmp_path):
    d = tmp_path / "pipeline_output"
    d.mkdir()
    return d


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


@pytest.mark.local
@pytest.mark.model
@pytest.mark.slow
class TestFullPipeline:
    def test_complete_pipeline_succeeds(self, hard_cut_video, output_root):
        """The full pipeline from source video → shots completes successfully."""
        result = run_omnishotcut_pipeline(
            video_id="test_full_pipeline",
            source_video_path=hard_cut_video,
            output_root=output_root,
            mode="clean_shot",
        )
        assert result.status == "SUCCEEDED", (
            f"Pipeline failed: {result.error_code} — {result.error_message}"
        )
        assert result.shot_count > 0
        assert result.runtime_ms > 0
        assert result.normalized_artifact_id
        assert result.shots_artifact_id

    def test_artifacts_persisted(self, hard_cut_video, output_root):
        """All expected artifact files are written to disk."""
        result = run_omnishotcut_pipeline(
            video_id="test_artifacts",
            source_video_path=hard_cut_video,
            output_root=output_root,
            mode="clean_shot",
        )
        assert result.status == "SUCCEEDED"

        # Check file existence
        base = (
            output_root
            / "projects"
            / "local_validation"
            / "videos"
            / "test_artifacts"
            / "artifacts"
        )

        norm_dir = list((base / "video_normalization").glob("*/"))
        assert len(norm_dir) > 0, "No normalization artifact dir found"
        norm_dir = norm_dir[0]

        assert (norm_dir / "normalized.mp4").exists(), "normalized.mp4 missing"
        assert (norm_dir / "normalized.mp4.manifest.json").exists(), "norm manifest missing"
        assert (norm_dir / "probe_before.json").exists(), "probe_before.json missing"
        assert (norm_dir / "probe_after.json").exists(), "probe_after.json missing"
        assert (norm_dir / "normalized_video.manifest.json").exists(), "custom manifest missing"

        shot_dir = list((base / "omnishotcut").glob("*/"))
        assert len(shot_dir) > 0, "No shot artifact dir found"
        shot_dir = shot_dir[0]

        assert (shot_dir / "shots.json").exists(), "shots.json missing"
        assert (shot_dir / "shots.json.manifest.json").exists(), "shots manifest missing"
        assert (shot_dir / "omnishotcut.raw.json").exists(), "raw inference output missing"

    def test_normalized_sha256_matches_file(self, hard_cut_video, output_root):
        """The SHA256 recorded in the result matches actual file content."""
        import hashlib

        result = run_omnishotcut_pipeline(
            video_id="test_sha256",
            source_video_path=hard_cut_video,
            output_root=output_root,
            mode="clean_shot",
        )
        assert result.status == "SUCCEEDED"

        norm_path = Path(result.normalized_artifact_uri)
        actual_sha = hashlib.sha256(norm_path.read_bytes()).hexdigest()
        assert result.normalized_sha256 == actual_sha

    def test_probe_before_after_recorded(self, hard_cut_video, output_root):
        """Probe before and after metadata is recorded in the result."""
        result = run_omnishotcut_pipeline(
            video_id="test_probes",
            source_video_path=hard_cut_video,
            output_root=output_root,
            mode="clean_shot",
        )
        assert result.status == "SUCCEEDED"
        assert result.probe_before is not None
        assert result.probe_after is not None
        assert result.probe_before["has_video"] is True
        assert result.probe_after["has_video"] is True


@pytest.mark.local
@pytest.mark.model
@pytest.mark.slow
class TestOmniShotCutInputRule:
    """Verify §14: OmniShotCut only reads normalized video, not original."""

    def test_result_references_normalized_uri(self, hard_cut_video, output_root):
        """The artifact URI points to normalized.mp4, not the original."""
        result = run_omnishotcut_pipeline(
            video_id="test_input_rule",
            source_video_path=hard_cut_video,
            output_root=output_root,
            mode="clean_shot",
        )
        assert result.status == "SUCCEEDED"
        # Normalized artifact URI should contain "normalized.mp4"
        assert "normalized" in result.normalized_artifact_uri.lower()
        # Should NOT be the original path
        assert result.normalized_artifact_uri != str(hard_cut_video)
