"""Unit tests for core.media — manifest generation."""

import json
import os
import tempfile

from core.media.schemas import FFprobeResult, NormalizationConfig, NormalizationResult
from core.media.normalization import _build_normalization_manifest


def _make_result(**kwargs) -> NormalizationResult:
    defaults = dict(
        input_path="/tmp/in.mp4",
        input_sha256="abcdef1234567890",
        output_path="/tmp/normalized.mp4",
        output_sha256="1234567890abcdef",
        output_size_bytes=1234567,
        probe_before=FFprobeResult(
            video_codec="h264",
            fps_num=30,
            fps_den=1,
            frame_rate_mode="CFR",
            duration_ms=5000,
            width=1920,
            height=1080,
        ),
        probe_before_path="/tmp/probe_before.json",
        probe_after=FFprobeResult(
            video_codec="h264",
            pixel_format="yuv420p",
            fps_num=30,
            fps_den=1,
            frame_rate_mode="CFR",
            duration_ms=5000,
            container_format="mov,mp4,m4a",
            width=1920,
            height=1080,
        ),
        probe_after_path="/tmp/probe_after.json",
        duration_delta_ms=0,
        validation_passed=True,
        ffmpeg_version="ffmpeg version 7.1.5",
        ffmpeg_command=["ffmpeg", "-i", "in.mp4", "out.mp4"],
        runtime_ms=1234,
        manifest_path="/tmp/manifest.json",
    )
    defaults.update(kwargs)
    return NormalizationResult(**defaults)


class TestBuildNormalizationManifest:
    def test_manifest_structure(self):
        cfg = NormalizationConfig()
        result = _make_result()
        manifest = _build_normalization_manifest(result, cfg)

        assert manifest["schema_version"] == "1.0"
        assert manifest["artifact_type"] == "normalized_video"
        assert manifest["producer"]["name"] == "ffmpeg_normalizer"
        assert manifest["producer"]["version"] == "1.0.0"
        assert manifest["producer"]["ffmpeg_version"] == "ffmpeg version 7.1.5"

    def test_normalization_section(self):
        cfg = NormalizationConfig()
        result = _make_result()
        manifest = _build_normalization_manifest(result, cfg)

        n = manifest["normalization"]
        assert n["container"] == "mp4"
        assert n["video_codec"] == "libx264"
        assert n["pixel_format"] == "yuv420p"
        assert n["frame_rate_mode"] == "cfr"
        assert n["audio_codec"] == "aac"
        assert n["audio_sample_rate"] == 48000

    def test_input_output_refs(self):
        cfg = NormalizationConfig()
        result = _make_result()
        manifest = _build_normalization_manifest(result, cfg)

        assert manifest["input"]["sha256"] == "abcdef1234567890"
        assert manifest["output"]["sha256"] == "1234567890abcdef"
        assert manifest["output"]["size_bytes"] == 1234567

    def test_fps_before_after(self):
        cfg = NormalizationConfig()
        result = _make_result()
        manifest = _build_normalization_manifest(result, cfg)

        assert manifest["input_fps"]["fps_num"] == 30
        assert manifest["input_fps"]["fps_den"] == 1
        assert manifest["output_fps"]["fps_num"] == 30
        assert manifest["output_fps"]["fps_den"] == 1

    def test_validation_status(self):
        cfg = NormalizationConfig()

        result_pass = _make_result(validation_passed=True)
        m = _build_normalization_manifest(result_pass, cfg)
        assert m["validation_passed"] is True
        assert m["validation_errors"] == []

        result_fail = _make_result(
            validation_passed=False,
            validation_errors=["duration delta exceeds tolerance"],
        )
        m2 = _build_normalization_manifest(result_fail, cfg)
        assert m2["validation_passed"] is False
        assert "duration delta" in m2["validation_errors"][0]

    def test_manifest_is_json_serializable(self):
        cfg = NormalizationConfig()
        result = _make_result()
        manifest = _build_normalization_manifest(result, cfg)
        json_str = json.dumps(manifest, indent=2)
        assert len(json_str) > 0
        reloaded = json.loads(json_str)
        assert reloaded["artifact_type"] == "normalized_video"

    def test_runtime_recorded(self):
        cfg = NormalizationConfig()
        result = _make_result(runtime_ms=5678)
        manifest = _build_normalization_manifest(result, cfg)
        assert manifest["runtime_ms"] == 5678

    def test_created_at_present(self):
        cfg = NormalizationConfig()
        result = _make_result()
        manifest = _build_normalization_manifest(result, cfg)
        assert "created_at" in manifest
        assert manifest["created_at"]  # non-empty ISO string
