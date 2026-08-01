"""OmniShotCut-specific exceptions."""

from core.exceptions import MovieAnalysisError


class OmniShotCutError(MovieAnalysisError):
    """Base exception for OmniShotCut adapter errors."""

    def __init__(self, message: str, code: str = "OMNISHOTCUT_ERROR") -> None:
        super().__init__(message, code=code)


class OmniShotCutImportError(OmniShotCutError):
    """Model package not installed or importable."""

    def __init__(self) -> None:
        super().__init__(
            "OmniShotCut is not installed. "
            "Run: pip install git+https://github.com/UVA-Computer-Vision-Lab/"
            "OmniShotCut.git@23ad6fb41b296fb9258b0e7825125a914573b906",
            code="OMNISHOTCUT_IMPORT_ERROR",
        )


class OmniShotCutWeightError(OmniShotCutError):
    """Model weights not found or incompatible."""

    def __init__(self, path: str) -> None:
        super().__init__(
            f"OmniShotCut weights not found at: {path}",
            code="OMNISHOTCUT_WEIGHT_ERROR",
        )


class OmniShotCutInferenceError(OmniShotCutError):
    """Inference failed."""

    def __init__(self, detail: str = "") -> None:
        super().__init__(
            f"OmniShotCut inference failed: {detail}",
            code="OMNISHOTCUT_INFERENCE_ERROR",
        )
