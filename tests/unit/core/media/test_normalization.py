"""Unit tests for core.media.normalization — validation logic.

Tests that do NOT require real FFmpeg/FFprobe:
  - validate_normalization() checks
  - NormalizationConfig defaults
  - Duration delta tolerance
"""

from core.media.normalization import validate_normalization
from core.media.schemas import FFprobeResult, NormalizationConfig


def _make_probe(
    duration_ms: int = 5000,
    fps_num: int = 30,
    fps_den: int = 1,
    codec: str = "h264",
    pixel_format: str = "yuv420p",
    container: str = "mov,mp4,m4a",
    has_video: bool = True,
    **kwargs,
) -> FFprobeResult:
    return FFprobeResult(
        video_codec=codec,
        pixel_format=pixel_format,
        fps_num=fps_num,
        fps_den=fps_den,
        frame_rate_mode="CFR",
        duration_ms=duration_ms,
        frame_count=int(duration_ms * fps_num / fps_den / 1000),
        start_time_ms=0,
        container_format=container,
        has_video=has_video,
        **kwargs,
    )


class TestValidateNormalization:
    def test_valid_normalization(self, tmp_path):
        """A properly normalized video passes validation."""
        output_file = tmp_path / "normalized.mp4"
        output_file.write_bytes(b"fake video content")

        before = _make_probe(duration_ms=5000)
        after = _make_probe(duration_ms=5000)

        errors = validate_normalization(
            probe_before=before,
            probe_after=after,
            output_path=str(output_file),
        )
        assert errors == []

    def test_output_file_missing(self):
        errors = validate_normalization(
            probe_before=_make_probe(),
            probe_after=_make_probe(),
            output_path="/nonexistent/file.mp4",
        )
        assert any("missing" in e.lower() for e in errors)

    def test_empty_output(self, tmp_path):
        output_file = tmp_path / "empty.mp4"
        output_file.write_bytes(b"")

        errors = validate_normalization(
            probe_before=_make_probe(),
            probe_after=_make_probe(),
            output_path=str(output_file),
        )
        assert any("empty" in e.lower() for e in errors)

    def test_no_video_stream(self, tmp_path):
        output_file = tmp_path / "out.mp4"
        output_file.write_bytes(b"content")

        errors = validate_normalization(
            probe_before=_make_probe(),
            probe_after=_make_probe(has_video=False),
            output_path=str(output_file),
        )
        assert any("video" in e.lower() for e in errors)

    def test_unreadable_codec(self, tmp_path):
        output_file = tmp_path / "out.mp4"
        output_file.write_bytes(b"content")

        errors = validate_normalization(
            probe_before=_make_probe(),
            probe_after=_make_probe(codec="unknown"),
            output_path=str(output_file),
        )
        assert any("codec" in e.lower() for e in errors)

    def test_duration_delta_within_tolerance(self, tmp_path):
        """Small duration drift is OK."""
        output_file = tmp_path / "out.mp4"
        output_file.write_bytes(b"content")

        before = _make_probe(duration_ms=5000)
        after = _make_probe(duration_ms=5030)  # 30ms drift < 100ms default

        errors = validate_normalization(
            probe_before=before,
            probe_after=after,
            output_path=str(output_file),
        )
        # 30ms delta against 30fps = 33ms per frame; max = max(100, 33) = 100
        assert not any("duration" in e.lower() for e in errors)

    def test_duration_delta_exceeds_tolerance(self, tmp_path):
        """Large duration drift should be rejected."""
        output_file = tmp_path / "out.mp4"
        output_file.write_bytes(b"content")

        before = _make_probe(duration_ms=5000)
        after = _make_probe(duration_ms=5200)  # 200ms drift

        errors = validate_normalization(
            probe_before=before,
            probe_after=after,
            output_path=str(output_file),
        )
        assert any("duration" in e.lower() for e in errors)

    def test_duration_zero(self, tmp_path):
        output_file = tmp_path / "out.mp4"
        output_file.write_bytes(b"content")

        errors = validate_normalization(
            probe_before=_make_probe(duration_ms=5000),
            probe_after=_make_probe(duration_ms=0),
            output_path=str(output_file),
        )
        assert any("duration" in e.lower() for e in errors)

    def test_pixel_format_mismatch(self, tmp_path):
        output_file = tmp_path / "out.mp4"
        output_file.write_bytes(b"content")

        errors = validate_normalization(
            probe_before=_make_probe(),
            probe_after=_make_probe(pixel_format="yuv422p"),
            output_path=str(output_file),
        )
        assert any("pixel" in e.lower() for e in errors)

    def test_wrong_container(self, tmp_path):
        output_file = tmp_path / "out.mkv"
        output_file.write_bytes(b"content")

        errors = validate_normalization(
            probe_before=_make_probe(),
            probe_after=_make_probe(container="matroska,webm"),
            output_path=str(output_file),
        )
        assert any("container" in e.lower() for e in errors)

    def test_custom_config_tolerance(self, tmp_path):
        """Custom config with tighter tolerance."""
        output_file = tmp_path / "out.mp4"
        output_file.write_bytes(b"content")

        before = _make_probe(duration_ms=5000)
        after = _make_probe(duration_ms=5060)  # 60ms drift

        config = NormalizationConfig(max_duration_delta_ms=50)
        errors = validate_normalization(
            probe_before=before,
            probe_after=after,
            output_path=str(output_file),
            config=config,
        )
        assert any("duration" in e.lower() for e in errors)
