"""Unit tests for core.media.schemas — FFprobeResult, NormalizationConfig, etc."""

import pytest

from core.media.schemas import FFprobeResult, NormalizationConfig, NormalizationResult


class TestFFprobeResult:
    def test_defaults(self):
        r = FFprobeResult()
        assert r.video_codec == "unknown"
        assert r.pixel_format == "unknown"
        assert r.fps_num == 24000
        assert r.fps_den == 1001
        assert r.frame_rate_mode == "CFR"
        assert r.has_video is True
        assert r.has_audio is False

    def test_fps_property(self):
        r = FFprobeResult(fps_num=30, fps_den=1)
        assert r.fps == 30.0

        r2 = FFprobeResult(fps_num=24000, fps_den=1001)
        assert pytest.approx(r2.fps, 0.01) == 23.976

    def test_fps_zero_den(self):
        r = FFprobeResult(fps_num=30, fps_den=0)
        assert r.fps == 0.0

    def test_duration_one_frame_ms(self):
        r = FFprobeResult(fps_num=30, fps_den=1)
        assert r.duration_one_frame_ms == 33  # 1000/30 ≈ 33ms

        r2 = FFprobeResult(fps_num=24000, fps_den=1001)
        assert r2.duration_one_frame_ms == 41  # (1001*1000)//24000 = 41

    def test_to_dict_excludes_raw_json(self):
        r = FFprobeResult(
            video_codec="h264",
            pixel_format="yuv420p",
            width=1920,
            height=1080,
            fps_num=30,
            fps_den=1,
            duration_ms=5000,
            frame_count=150,
            raw_json={"format": {}, "streams": []},
        )
        d = r.to_dict()
        assert "raw_json" not in d
        assert d["video_codec"] == "h264"
        assert d["width"] == 1920
        assert d["fps_num"] == 30


class TestNormalizationConfig:
    def test_defaults(self):
        cfg = NormalizationConfig()
        assert cfg.container == "mp4"
        assert cfg.video_codec == "libx264"
        assert cfg.pixel_format == "yuv420p"
        assert cfg.frame_rate_mode == "cfr"
        assert cfg.audio_codec == "aac"
        assert cfg.audio_sample_rate == 48000
        assert cfg.faststart is True
        assert cfg.normalize_timestamps is True
        assert cfg.max_duration_delta_ms == 100

    def test_movflags(self):
        cfg = NormalizationConfig(faststart=True)
        assert "+faststart" in cfg.movflags

        cfg2 = NormalizationConfig(faststart=False)
        assert "+faststart" not in cfg2.movflags


class TestNormalizationResult:
    def test_default_validation_errors(self):
        r = NormalizationResult(
            input_path="/tmp/in.mp4",
            input_sha256="abc",
            output_path="/tmp/out.mp4",
            output_sha256="def",
            output_size_bytes=1000,
            probe_before=FFprobeResult(),
            probe_after=FFprobeResult(),
        )
        assert r.validation_passed is False
        assert r.validation_errors == []
        assert r.duration_delta_ms == 0
