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
    """Raised by Celery tasks on non-retryable failures.

    Unlike returning a {"status": "FAILED"} dict (which Celery treats as
    a successful return and continues the chain), this exception causes
    Celery to mark the task as FAILURE and stops the chain.
    """
