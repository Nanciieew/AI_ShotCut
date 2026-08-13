"""
Base Model Adapter — abstract interface for all AI models.

Every external model MUST be accessed through an Adapter that
implements this base class. Upper-layer code MUST NOT call
third-party model APIs directly.

See: 架构规范 §3.4, §8
"""

from abc import ABC, abstractmethod
from typing import Any


class BaseModelAdapter(ABC):
    """Abstract base for all model adapters.

    Each concrete adapter wraps a specific model (FFmpeg Scene, Doubao ASR,
    Scene Boundary, etc.) and enforces the unified
    input/output contract defined in 输入输出规范.md.

    Attributes:
        name: Human-readable model identifier (e.g. "ffmpeg_scene").
        version: Pinned model version (e.g. "1.0.0").
    """

    name: str
    version: str

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    @abstractmethod
    def load(self) -> None:
        """Load model weights and allocate resources.

        Called once when the worker starts or when the model is
        first needed. Must be idempotent — calling load() on an
        already-loaded model is safe.
        """
        ...

    @abstractmethod
    def unload(self) -> None:
        """Release model resources (GPU memory, file handles, etc.).

        Called on worker shutdown or when the model is no longer
        needed.
        """
        ...

    # ------------------------------------------------------------------
    # Core
    # ------------------------------------------------------------------

    @abstractmethod
    def predict(self, model_input: dict[str, Any]) -> dict[str, Any]:
        """Run inference and return a unified-format result.

        The input dict follows the standard model input contract
        (see 输入输出规范.md §通用输入外壳).

        The returned dict follows the standard success or failure
        output contract (see 输入输出规范.md §通用输出).
        """
        ...

    # ------------------------------------------------------------------
    # Health
    # ------------------------------------------------------------------

    @abstractmethod
    def health_check(self) -> bool:
        """Return True if the model is loaded, responsive, and ready
        to accept predict() calls."""
        ...
