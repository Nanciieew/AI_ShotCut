"""Core Media module — FFmpeg / FFprobe wrappers and video normalization.

This module provides the canonical, shared implementation for:
  - FFprobe metadata extraction (structured output)
  - FFmpeg command building and execution
  - Video normalization pipeline (probe → normalize → validate)
  - Normalization result schemas and manifest generation

All FFmpeg/FFprobe calls MUST go through this module.
No task module should shell out to ffmpeg/ffprobe directly.
"""

from core.media.schemas import FFprobeResult, NormalizationConfig, NormalizationResult
from core.media.ffprobe import run_ffprobe, probe_video
from core.media.ffmpeg import build_normalize_command, run_ffmpeg
from core.media.normalization import normalize_video_file, validate_normalization
from core.media.exceptions import (
    MediaError,
    FFprobeError,
    FFmpegError,
    NormalizationError,
    NormalizationValidationError,
)

__all__ = [
    # schemas
    "FFprobeResult",
    "NormalizationConfig",
    "NormalizationResult",
    # ffprobe
    "run_ffprobe",
    "probe_video",
    # ffmpeg
    "build_normalize_command",
    "run_ffmpeg",
    # normalization
    "normalize_video_file",
    "validate_normalization",
    # exceptions
    "MediaError",
    "FFprobeError",
    "FFmpegError",
    "NormalizationError",
    "NormalizationValidationError",
]
