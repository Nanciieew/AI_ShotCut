"""Unit tests for core.media.ffmpeg — command building.

Tests that do NOT require real FFmpeg:
  - build_normalize_command() parameter construction
  - No shell=True
  - Audio handling (with/without audio)
  - Timestamp normalization
"""

from core.media.ffmpeg import build_normalize_command, get_ffmpeg_version
from core.media.schemas import FFprobeResult, NormalizationConfig


def _make_probe(
    has_audio: bool = True,
    fps_num: int = 30,
    fps_den: int = 1,
    width: int = 1920,
    height: int = 1080,
) -> FFprobeResult:
    return FFprobeResult(
        video_codec="h264",
        pixel_format="yuv420p",
        fps_num=fps_num,
        fps_den=fps_den,
        frame_rate_mode="CFR",
        width=width,
        height=height,
        has_audio=has_audio,
        audio_codec="aac" if has_audio else None,
        audio_sample_rate=48000 if has_audio else None,
    )


class TestBuildNormalizeCommand:
    def test_basic_command_structure(self):
        """Command should start with ffmpeg, use parameter list."""
        cmd = build_normalize_command(
            input_path="/tmp/in.mp4",
            output_path="/tmp/out.mp4",
            probe=_make_probe(),
        )
        assert cmd[0] == "ffmpeg"
        assert "-hide_banner" in cmd
        assert "-y" in cmd
        assert "-i" in cmd
        assert "/tmp/in.mp4" in cmd
        assert "/tmp/out.mp4" == cmd[-1]
        # Should not use shell=True style (all individual args)
        assert all(" " not in arg for arg in cmd[1:])
        # Check for shell injection safety
        assert ";" not in " ".join(cmd)

    def test_video_codec_params(self):
        cmd = build_normalize_command(
            input_path="/tmp/in.mp4",
            output_path="/tmp/out.mp4",
            probe=_make_probe(),
        )
        assert "-c:v" in cmd
        idx = cmd.index("-c:v")
        assert cmd[idx + 1] == "libx264"
        assert "-pix_fmt" in cmd
        assert "yuv420p" in cmd
        assert "-vsync" in cmd
        assert "cfr" in cmd

    def test_with_audio(self):
        cmd = build_normalize_command(
            input_path="/tmp/in.mp4",
            output_path="/tmp/out.mp4",
            probe=_make_probe(has_audio=True),
        )
        assert "-c:a" in cmd
        assert "aac" in cmd
        assert "-ar" in cmd
        assert "48000" in cmd

    def test_without_audio(self):
        """When probe reports no audio, audio encoding params are omitted."""
        cmd = build_normalize_command(
            input_path="/tmp/in.mp4",
            output_path="/tmp/out.mp4",
            probe=_make_probe(has_audio=False),
        )
        assert "-c:a" not in cmd

    def test_map_audio_optional(self):
        """-map 0:a:0? should be in command (optional audio)."""
        cmd = build_normalize_command(
            input_path="/tmp/in.mp4",
            output_path="/tmp/out.mp4",
            probe=_make_probe(),
        )
        assert "-map" in cmd
        assert "0:a:0?" in cmd

    def test_faststart_enabled(self):
        cmd = build_normalize_command(
            input_path="/tmp/in.mp4",
            output_path="/tmp/out.mp4",
            probe=_make_probe(),
        )
        assert "-movflags" in cmd
        assert "+faststart" in cmd

    def test_faststart_disabled(self):
        config = NormalizationConfig(faststart=False)
        cmd = build_normalize_command(
            input_path="/tmp/in.mp4",
            output_path="/tmp/out.mp4",
            probe=_make_probe(),
            config=config,
        )
        assert "+faststart" not in cmd

    def test_avoid_negative_ts(self):
        cmd = build_normalize_command(
            input_path="/tmp/in.mp4",
            output_path="/tmp/out.mp4",
            probe=_make_probe(),
        )
        assert "-avoid_negative_ts" in cmd
        assert "make_zero" in cmd

    def test_does_not_force_fps(self):
        """The command should NOT include -r (hardcoded FPS override).
        FPS is preserved from the source via -vsync cfr only."""
        cmd = build_normalize_command(
            input_path="/tmp/in.mp4",
            output_path="/tmp/out.mp4",
            probe=_make_probe(),
        )
        assert "-r" not in cmd, (
            "Command should NOT include -r to force a different FPS. "
            "Use -vsync cfr to preserve source FPS."
        )

    def test_scale_to_even_dimensions(self):
        cmd = build_normalize_command(
            input_path="/tmp/in.mp4",
            output_path="/tmp/out.mp4",
            probe=_make_probe(width=1921, height=1079),
        )
        assert "-vf" in cmd
        vf_idx = cmd.index("-vf")
        vf_value = cmd[vf_idx + 1]
        assert "trunc(iw/2)*2" in vf_value
        assert "trunc(ih/2)*2" in vf_value

    def test_paths_with_spaces(self):
        """Paths with spaces should work as separate arguments."""
        cmd = build_normalize_command(
            input_path="/tmp/my video.mp4",
            output_path="/tmp/out video.mp4",
            probe=_make_probe(),
        )
        assert "/tmp/my video.mp4" in cmd
        assert "/tmp/out video.mp4" in cmd


class TestFFmpegVersion:
    def test_get_version_returns_string(self):
        ver = get_ffmpeg_version()
        # Should return empty string if ffmpeg not installed
        assert isinstance(ver, str)

    def test_get_version_custom_binary(self):
        ver = get_ffmpeg_version(ffmpeg_bin="/nonexistent/ffmpeg")
        assert ver == ""
