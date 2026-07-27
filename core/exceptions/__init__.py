"""
Custom exception classes for the Movie Analysis Platform.

All application-level errors should derive from MovieAnalysisError
so they can be caught and handled uniformly by middleware.
"""


class MovieAnalysisError(Exception):
    """Base exception for all application-level errors."""

    def __init__(self, message: str, code: str = "INTERNAL_ERROR") -> None:
        super().__init__(message)
        self.code = code


class VideoDecodeError(MovieAnalysisError):
    """Raised when FFmpeg cannot decode the input video."""

    def __init__(self, message: str = "FFmpeg could not decode the input video.") -> None:
        super().__init__(message, code="VIDEO_DECODE_FAILED")


class VideoNotFoundError(MovieAnalysisError):
    """Raised when a video_id does not exist."""

    def __init__(self, video_id: str) -> None:
        super().__init__(
            f"Video not found: {video_id}",
            code="VIDEO_NOT_FOUND",
        )


class TaskNotFoundError(MovieAnalysisError):
    """Raised when a task_id does not exist."""

    def __init__(self, task_id: str) -> None:
        super().__init__(
            f"Task not found: {task_id}",
            code="TASK_NOT_FOUND",
        )


class ModelNotAvailableError(MovieAnalysisError):
    """Raised when a requested model is not enabled or not healthy."""

    def __init__(self, model_name: str) -> None:
        super().__init__(
            f"Model not available: {model_name}",
            code="MODEL_NOT_AVAILABLE",
        )


class ModelInferenceError(MovieAnalysisError):
    """Raised when a model fails during inference."""

    def __init__(self, model_name: str, detail: str = "") -> None:
        super().__init__(
            f"Model inference failed: {model_name}. {detail}",
            code="MODEL_INFERENCE_FAILED",
        )


class SchemaValidationError(MovieAnalysisError):
    """Raised when data does not conform to the expected schema."""

    def __init__(self, detail: str = "") -> None:
        super().__init__(
            f"Schema validation error: {detail}",
            code="SCHEMA_VALIDATION_FAILED",
        )


class StorageError(MovieAnalysisError):
    """Raised when a storage operation fails."""

    def __init__(self, detail: str = "") -> None:
        super().__init__(
            f"Storage error: {detail}",
            code="STORAGE_ERROR",
        )


class ConfigurationError(MovieAnalysisError):
    """Raised when required configuration is missing or invalid."""

    def __init__(self, detail: str = "") -> None:
        super().__init__(
            f"Configuration error: {detail}",
            code="CONFIGURATION_ERROR",
        )
