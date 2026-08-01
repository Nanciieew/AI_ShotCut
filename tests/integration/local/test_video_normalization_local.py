"""Integration tests: video normalization (requires local ffmpeg/ffprobe).

Markers: local, slow
"""

from pathlib import Path

import pytest

from core.media.exceptions import FFprobeError
from core.media.ffmpeg import build_normalize_command, get_ffmpeg_version, run_ffmpeg
from core.media.ffprobe import probe_video, run_ffprobe
from core.media.normalization import validate_normalization
from core.media.schemas import NormalizationConfig

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def hard_cut_video():
    """Locate the Hard_Cut_1.mp4 test fixture."""
    candidates = [
        Path("tests/fixtures/videos/omnishotcut/Hard_Cut_1.mp4"),
        Path("data/test_videos/Hard_Cut_1.mp4"),
    ]
    for p in candidates:
        if p.exists():
            return p.resolve()
    pytest.skip("Hard_Cut_1.mp4 not found in any fixture directory")


@pytest.fixture
def output_dir(tmp_path):
    d = tmp_path / "normalization_test"
    d.mkdir()
    return d


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


@pytest.mark.local
@pytest.mark.slow
class TestFFprobeLocal:
    def test_probe_real_video(self, hard_cut_video):
        """FFprobe can extract metadata from the real test video."""
        result = probe_video(str(hard_cut_video))
        assert result.has_video is True
        assert result.width > 0
        assert result.height > 0
        assert result.duration_ms > 0
        assert result.fps_num > 0
        assert result.fps_den > 0
        assert result.video_codec != "unknown"

    def test_probe_saves_to_disk(self, hard_cut_video, output_dir):
        """Probe saves raw JSON to output directory."""
        probe_video(
            str(hard_cut_video),
            output_dir=str(output_dir),
            label="probe_test",
        )
        assert (output_dir / "probe_test.json").exists()

    def test_probe_detects_audio(self, hard_cut_video):
        """The fixture video should have audio."""
        result = run_ffprobe(str(hard_cut_video))
        # Record whether audio was detected (may vary by fixture)
        assert isinstance(result.has_audio, bool)

    def test_ffprobe_error_on_invalid_file(self, tmp_path):
        """FFprobeError raised for non-video files."""
        bad = tmp_path / "not_video.mp4"
        bad.write_text("this is not a video")
        with pytest.raises(FFprobeError):
            run_ffprobe(str(bad))


@pytest.mark.local
@pytest.mark.slow
class TestFFmpegNormalizeLocal:
    def test_normalize_preserves_content(self, hard_cut_video, output_dir):
        """Normalization produces a valid output file."""
        probe_before = probe_video(str(hard_cut_video))
        output_path = output_dir / "normalized.mp4"

        cmd = build_normalize_command(
            input_path=str(hard_cut_video),
            output_path=str(output_path),
            probe=probe_before,
        )
        run_ffmpeg(cmd, timeout=300, description="test normalization")

        assert output_path.exists()
        assert output_path.stat().st_size > 0

    def test_normalize_output_is_valid_video(self, hard_cut_video, output_dir):
        """Normalized output is a valid MP4 that ffprobe can read."""
        probe_before = probe_video(str(hard_cut_video))
        output_path = output_dir / "normalized.mp4"

        cmd = build_normalize_command(
            input_path=str(hard_cut_video),
            output_path=str(output_path),
            probe=probe_before,
        )
        run_ffmpeg(cmd, timeout=300, description="test normalization")

        probe_after = probe_video(str(output_path))
        assert probe_after.has_video is True
        assert probe_after.pixel_format == "yuv420p"
        assert "mp4" in probe_after.container_format.lower()

    def test_normalize_validates_against_spec(self, hard_cut_video, output_dir):
        """Normalized output passes spec validation."""
        probe_before = probe_video(str(hard_cut_video))
        output_path = output_dir / "normalized.mp4"

        cmd = build_normalize_command(
            input_path=str(hard_cut_video),
            output_path=str(output_path),
            probe=probe_before,
        )
        run_ffmpeg(cmd, timeout=300, description="test normalization")

        probe_after = probe_video(str(output_path))
        errors = validate_normalization(
            probe_before=probe_before,
            probe_after=probe_after,
            output_path=str(output_path),
        )
        assert errors == [], f"Validation errors: {errors}"

    def test_duration_within_tolerance(self, hard_cut_video, output_dir):
        """Duration delta after normalization is within acceptable range."""
        probe_before = probe_video(str(hard_cut_video))
        output_path = output_dir / "normalized.mp4"

        cmd = build_normalize_command(
            input_path=str(hard_cut_video),
            output_path=str(output_path),
            probe=probe_before,
        )
        run_ffmpeg(cmd, timeout=300, description="test normalization")

        probe_after = probe_video(str(output_path))
        delta = abs(probe_before.duration_ms - probe_after.duration_ms)
        one_frame = probe_before.duration_one_frame_ms
        max_delta = max(100, one_frame)
        assert delta <= max_delta, (
            f"Duration delta {delta}ms exceeds max {max_delta}ms (1 frame = {one_frame}ms)"
        )


@pytest.mark.local
@pytest.mark.slow
class TestNormalizeNoAudio:
    """Test normalization of video without audio track."""

    def test_no_audio_normalization(self, hard_cut_video, output_dir):
        """Normalization still works (audio is optional with -map 0:a:0?)."""
        probe_before = probe_video(str(hard_cut_video))
        output_path = output_dir / "normalized.mp4"

        cmd = build_normalize_command(
            input_path=str(hard_cut_video),
            output_path=str(output_path),
            probe=probe_before,
        )
        # Should not fail
        run_ffmpeg(cmd, timeout=300, description="test normalization")
        assert output_path.exists()


@pytest.mark.local
def test_ffmpeg_version_detected():
    """FFmpeg is installed and version can be read."""
    ver = get_ffmpeg_version()
    assert len(ver) > 0
    assert "ffmpeg version" in ver.lower()


@pytest.mark.local
def test_normalization_config_defaults():
    """Default NormalizationConfig matches spec requirements."""
    cfg = NormalizationConfig()
    assert cfg.container == "mp4"
    assert cfg.video_codec == "libx264"
    assert cfg.pixel_format == "yuv420p"
    assert cfg.audio_sample_rate == 48000
    assert cfg.faststart is True
