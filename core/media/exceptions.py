"""Media processing exceptions."""


class MediaError(Exception):
    """Base exception for media processing errors."""


class FFprobeError(MediaError):
    """FFprobe failed to extract metadata."""


class FFmpegError(MediaError):
    """FFmpeg command execution failed."""


class NormalizationError(MediaError):
    """Video normalization pipeline failed."""


class NormalizationValidationError(MediaError):
    """Normalization output failed post-validation checks."""


class KeyframeExtractionError(MediaError):
    """Keyframe extraction failed (decode, encode, or I/O error)."""


class NonRetryableTaskError(Exception):
    """Raised by Workflow steps when retrying cannot produce a valid result."""
