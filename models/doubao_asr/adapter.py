"""Doubao SeedASR Adapter — wraps SeedASRProvider per BaseModelAdapter contract.

IO_Rule §4.2: audio_url → subtitle_segments

Per §7.2: Adapter ONLY receives pre-built audio_url from the caller.
It does NOT call FFmpeg, read STORAGE_ROOT, or construct public URLs.
Audio extraction and URL signing are Workflow/StorageService responsibilities.
"""

from __future__ import annotations

import logging
import time
from typing import Any

from models.base.adapter import BaseModelAdapter
from models.doubao_asr.providers.seedasr import SeedASRProvider

logger = logging.getLogger(__name__)


class DoubaoASRAdapter(BaseModelAdapter):
    """Doubao SeedASR adapter — receives audio_url, returns subtitle segments."""

    name = "doubao_asr"
    version = "1.0.0"

    def __init__(self) -> None:
        self._provider: SeedASRProvider | None = None
        self._loaded = False
        self._last_segments: list[dict] = []

    # ------------------------------------------------------------------
    # BaseModelAdapter interface
    # ------------------------------------------------------------------

    def load(self, api_key: str | None = None) -> None:  # noqa: ARG002
        if self._loaded:
            return
        self._provider = SeedASRProvider()
        self._loaded = True

    def unload(self) -> None:
        self._provider = None
        self._loaded = False

    def predict(self, model_input: dict[str, Any]) -> dict[str, Any]:
        """Run transcription.

        Input (§7.2):
          input.audio_url  — public HTTP URL to audio file (REQUIRED)

        Output:
          {status, artifacts: {subtitle_segments: [...]}, metrics, error}
        """
        if not self._loaded:
            self.load()
        provider = self._provider
        if provider is None:
            return self._error("PROVIDER_NOT_LOADED", "SeedASR provider is not loaded")

        task_id = model_input.get("task_id", "unknown")
        video_id = model_input.get("video_id", "unknown")
        params = model_input.get("parameters", {})
        audio_input = model_input.get("input", {})

        audio_url = audio_input.get("audio_url", "")
        language = params.get("language", "zh-CN")

        if not audio_url:
            return self._error(
                "NO_AUDIO_URL",
                "Provide input.audio_url — caller must build public URL via StorageService",
            )

        try:
            t0 = time.monotonic()
            raw = provider.transcribe(audio_url, language=language)
            runtime_ms = int((time.monotonic() - t0) * 1000)
        except Exception as e:
            return self._error("TRANSCRIPTION_FAILED", str(e))

        segments = self._build_segments(raw, video_id, language)

        return {
            "task_id": task_id,
            "video_id": video_id,
            "status": "SUCCEEDED",
            "artifacts": {"subtitle_segments": segments},
            "metrics": {
                "segment_count": len(segments),
                "runtime_ms": runtime_ms,
                "language": language,
            },
        }

    def health_check(self) -> bool:
        return self._provider is not None and self._provider.health_check()

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _build_segments(api_result: dict, video_id: str, language: str | None) -> list[dict]:
        segments: list[dict] = []
        results = api_result.get("result", {})
        if isinstance(results, dict):
            results = [results]

        for r in results:
            utterances = r.get("utterances", [])
            if utterances:
                for i, u in enumerate(utterances):
                    segments.append(
                        {
                            "subtitle_id": f"subtitle_{i + 1:06d}",
                            "video_id": video_id,
                            "start_ms": u.get("start_time", 0),
                            "end_ms": u.get("end_time", 0),
                            "text": (u.get("text", "")).strip(),
                            "language": language or "zh-CN",
                            "confidence": 0.95 if u.get("definite") else 0.7,
                        }
                    )
                continue

            text = r.get("text", "")
            if text.strip() and not segments:
                segments.append(
                    {
                        "subtitle_id": "subtitle_000001",
                        "video_id": video_id,
                        "start_ms": 0,
                        "end_ms": 0,
                        "text": text.strip(),
                        "language": language or "zh-CN",
                        "confidence": 0.7,
                    }
                )

        return segments

    @staticmethod
    def _error(code: str, message: str) -> dict:
        return {
            "status": "FAILED",
            "error": {"code": code, "message": message, "retryable": False},
        }
