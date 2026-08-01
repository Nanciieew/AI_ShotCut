"""Unit tests for core.media.ffprobe — probe output parsing.

Tests that do NOT require actual FFprobe binary:
  - JSON parsing logic
  - Error handling for missing files
  - Structured output format
"""

import json

import pytest

from core.media.exceptions import FFprobeError
from core.media.ffprobe import _parse_ffprobe_output, run_ffprobe

# ---------------------------------------------------------------------------
# Sample ffprobe JSON fixtures
# ---------------------------------------------------------------------------

SAMPLE_FFPROBE_JSON = {
    "format": {
        "filename": "/tmp/test.mp4",
        "format_name": "mov,mp4,m4a,3gp,3g2,mj2",
        "duration": "10.500000",
        "start_time": "0.000000",
    },
    "streams": [
        {
            "codec_type": "video",
            "codec_name": "h264",
            "pix_fmt": "yuv420p",
            "width": 1920,
            "height": 1080,
            "r_frame_rate": "30/1",
            "avg_frame_rate": "30/1",
            "nb_frames": "315",
        },
        {
            "codec_type": "audio",
            "codec_name": "aac",
            "sample_rate": "48000",
        },
    ],
}

SAMPLE_FFPROBE_JSON_NO_AUDIO = {
    "format": {
        "format_name": "mp4",
        "duration": "5.000000",
    },
    "streams": [
        {
            "codec_type": "video",
            "codec_name": "h264",
            "pix_fmt": "yuv420p",
            "width": 1280,
            "height": 720,
            "r_frame_rate": "24000/1001",
            "avg_frame_rate": "24000/1001",
            "nb_frames": "120",
        },
    ],
}

SAMPLE_FFPROBE_JSON_VFR = {
    "format": {
        "format_name": "matroska,webm",
        "duration": "8.000000",
    },
    "streams": [
        {
            "codec_type": "video",
            "codec_name": "vp9",
            "pix_fmt": "yuv420p",
            "width": 640,
            "height": 480,
            "r_frame_rate": "30/1",
            "avg_frame_rate": "29970/1000",
            "nb_frames": "240",
        },
    ],
}

SAMPLE_FFPROBE_JSON_NEGATIVE_START = {
    "format": {
        "format_name": "mp4",
        "duration": "7.200000",
        "start_time": "-0.040000",
    },
    "streams": [
        {
            "codec_type": "video",
            "codec_name": "h264",
            "pix_fmt": "yuv420p",
            "width": 1920,
            "height": 1080,
            "r_frame_rate": "24/1",
            "avg_frame_rate": "24/1",
            "nb_frames": "173",
        },
    ],
}


# ---------------------------------------------------------------------------
# Parsing tests
# ---------------------------------------------------------------------------


class TestParseFFprobeOutput:
    def test_basic_video_stream(self):
        result = _parse_ffprobe_output(SAMPLE_FFPROBE_JSON)
        assert result.has_video is True
        assert result.has_audio is True
        assert result.video_codec == "h264"
        assert result.pixel_format == "yuv420p"
        assert result.width == 1920
        assert result.height == 1080
        assert result.fps_num == 30
        assert result.fps_den == 1
        assert result.duration_ms == 10500
        assert result.frame_count == 315
        assert result.start_time_ms == 0
        assert result.audio_codec == "aac"
        assert result.audio_sample_rate == 48000
        assert result.frame_rate_mode == "CFR"

    def test_no_audio_stream(self):
        result = _parse_ffprobe_output(SAMPLE_FFPROBE_JSON_NO_AUDIO)
        assert result.has_video is True
        assert result.has_audio is False
        assert result.audio_codec is None
        assert result.fps_num == 24000
        assert result.fps_den == 1001
        assert result.frame_count == 120

    def test_vfr_detection(self):
        """VFR when r_frame_rate != avg_frame_rate."""
        result = _parse_ffprobe_output(SAMPLE_FFPROBE_JSON_VFR)
        assert result.frame_rate_mode == "VFR"
        assert result.video_codec == "vp9"
        assert result.width == 640
        assert result.height == 480

    def test_negative_start_time(self):
        result = _parse_ffprobe_output(SAMPLE_FFPROBE_JSON_NEGATIVE_START)
        assert result.start_time_ms == -40

    def test_unknown_fields_default(self):
        result = _parse_ffprobe_output({"format": {}, "streams": []})
        assert result.has_video is True  # default
        assert result.has_audio is False
        assert result.video_codec == "unknown"
        assert result.duration_ms == 0
        assert result.frame_count == 0

    def test_raw_json_preserved(self):
        result = _parse_ffprobe_output(SAMPLE_FFPROBE_JSON)
        assert result.raw_json is not None
        assert result.raw_json["format"]["duration"] == "10.500000"

    def test_duration_estimation_from_fps(self):
        """If nb_frames is missing, estimate from duration × fps."""
        data = {
            "format": {"format_name": "mp4", "duration": "2.000000"},
            "streams": [
                {
                    "codec_type": "video",
                    "codec_name": "h264",
                    "r_frame_rate": "30/1",
                },
            ],
        }
        result = _parse_ffprobe_output(data)
        # fps should be parsed correctly from r_frame_rate
        assert result.fps_num == 30
        assert result.fps_den == 1
        assert result.duration_ms == 2000
        assert result.frame_count > 0  # estimation ran
        assert result.duration_ms == 2000


# ---------------------------------------------------------------------------
# Error handling tests (without real ffprobe)
# ---------------------------------------------------------------------------


class TestFFprobeErrorHandling:
    def test_missing_file(self):
        with pytest.raises(FFprobeError, match="not found"):
            run_ffprobe("/nonexistent/path/video.mp4")

    def test_ffprobe_not_installed(self):
        """When ffprobe binary doesn't exist."""
        with pytest.raises(FFprobeError, match="not found"):
            run_ffprobe(
                __file__,  # use an existing file (this test file)
                ffprobe_bin="/nonexistent/ffprobe",
            )


# ---------------------------------------------------------------------------
# to_dict / serialization tests
# ---------------------------------------------------------------------------


class TestFFprobeSerialization:
    def test_to_dict_json_roundtrip(self):
        result = _parse_ffprobe_output(SAMPLE_FFPROBE_JSON)
        d = result.to_dict()
        # Should be JSON-serializable
        json_str = json.dumps(d)
        reloaded = json.loads(json_str)
        assert reloaded["video_codec"] == "h264"
        assert reloaded["fps_num"] == 30
        assert reloaded["duration_ms"] == 10500
