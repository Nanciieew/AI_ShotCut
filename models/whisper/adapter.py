"""Whisper model adapter — speech-to-text transcription.

Implements the BaseModelAdapter interface for OpenAI Whisper.
Follows IO_Rule §4.2 contract.

Weights: auto-download from HuggingFace Hub (openai/whisper-base by default).
         Override with WHISPER_MODEL env var (tiny/base/small/medium/large-v3).
"""

from __future__ import annotations

import json
import os
import subprocess
import tempfile
import time
import uuid
from pathlib import Path
from typing import Any

from models.base.adapter import BaseModelAdapter


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

FIXED_COMMIT = "v20240930"  # openai/whisper release tag
DEFAULT_MODEL = "base"  # CPU-friendly default; override with WHISPER_MODEL env
HUGGINGFACE_REPO = "openai/whisper-base"  # HF pattern — dynamic by model size


# ---------------------------------------------------------------------------
# Adapter
# ---------------------------------------------------------------------------


class WhisperAdapter(BaseModelAdapter):
    """Whisper speech-to-text adapter.

    Loads a Whisper model from HuggingFace, runs transcription on an
    audio file extracted from the normalized video, and returns timed
    subtitle segments per IO_Rule §4.2.

    Parameters
    ----------
    model_size : str
        Whisper model size: tiny, base, small, medium, large-v3.
        Default from WHISPER_MODEL env var, or "base".
    """

    name = "whisper"
    version = "1.0.0"

    def __init__(self, model_size: str | None = None) -> None:
        self._model_size = model_size or os.getenv("WHISPER_MODEL", DEFAULT_MODEL)
        self._model: Any = None
        self._loaded = False

    # ------------------------------------------------------------------
    # BaseModelAdapter interface
    # ------------------------------------------------------------------

    def load(self) -> None:
        """Load the Whisper model from HuggingFace Hub."""
        if self._loaded:
            return

        import whisper

        model_tag = getattr(self, "_model_size", DEFAULT_MODEL)
        print(f"Loading Whisper {model_tag} from HuggingFace ...")
        self._model = whisper.load_model(model_tag)
        self._loaded = True
        print(f"Whisper {model_tag} loaded successfully.")

    def unload(self) -> None:
        """Free the Whisper model from memory."""
        self._model = None
        self._loaded = False

    def predict(self, model_input: dict) -> dict:
        """Run transcription and return IO_Rule §2 compliant output.

        Parameters
        ----------
        model_input : dict
            IO_Rule §1 unified input shell:
            {
                "schema_version": "1.0",
                "task_id": "...",
                "video_id": "...",
                "model": {"name": "whisper", "version": "..."},
                "input": {
                    "audio_uri": "storage://.../audio.wav",
                    -- or --
                    "video_uri": "storage://.../normalized.mp4"
                },
                "parameters": {
                    "language": "zh",          # optional
                    "word_timestamps": true    # optional
                }
            }

        Returns
        -------
        dict
            IO_Rule §2 output:
            {
                "status": "SUCCEEDED" | "FAILED",
                "artifacts": {"subtitles": "storage://..."},
                "metrics": {"segment_count": N, "runtime_ms": M},
                "error": {"code": "...", "message": "..."}  # only if FAILED
            }
        """
        if not self._loaded or self._model is None:
            return self._error("MODEL_NOT_LOADED", "Call load() before predict().")

        task_id = model_input.get("task_id", "unknown")
        video_id = model_input.get("video_id", "unknown")
        params = model_input.get("parameters", {})

        # --- Resolve audio source ---
        audio_input = model_input.get("input", {})
        audio_uri = audio_input.get("audio_uri")
        video_uri = audio_input.get("video_uri")

        if audio_uri:
            audio_path = self._resolve_uri(audio_uri)
        elif video_uri:
            # Extract audio from normalized video
            audio_path = self._extract_audio(video_uri)
            if audio_path is None:
                return self._error(
                    "AUDIO_EXTRACTION_FAILED",
                    "Failed to extract audio from normalized video.",
                )
        else:
            return self._error(
                "NO_AUDIO_INPUT",
                "Provide audio_uri or video_uri in model_input.input.",
            )

        if not os.path.exists(audio_path):
            return self._error(
                "AUDIO_NOT_FOUND",
                f"Audio file not found: {audio_path}",
            )

        # --- Run transcription ---
        transcribe_options: dict = {
            "word_timestamps": params.get("word_timestamps", True),
        }
        if params.get("language"):
            transcribe_options["language"] = params["language"]

        try:
            t_start = time.monotonic()
            result = self._model.transcribe(audio_path, **transcribe_options)
            runtime_ms = int((time.monotonic() - t_start) * 1000)
        except Exception as e:
            return self._error("TRANSCRIPTION_FAILED", str(e))

        # --- Convert to subtitle segments ---
        segments = self._build_segments(result, video_id, params.get("language"))

        # --- Build IO_Rule output ---
        return {
            "task_id": task_id,
            "video_id": video_id,
            "status": "SUCCEEDED",
            "artifacts": {
                "subtitle_segments": segments,
            },
            "metrics": {
                "segment_count": len(segments),
                "runtime_ms": runtime_ms,
                "language": result.get("language", "unknown"),
            },
        }

    def health_check(self) -> dict:
        """Report model health status."""
        return {
            "model": "whisper",
            "version": self.version,
            "model_size": self._model_size,
            "loaded": self._loaded,
            "status": "healthy" if self._loaded else "not_loaded",
        }

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _resolve_uri(self, uri: str) -> str:
        """Convert storage:// URI to local absolute path."""
        storage_root = os.getenv("STORAGE_ROOT", "./data")
        prefix = "storage://"
        if uri.startswith(prefix):
            return os.path.join(storage_root, uri[len(prefix) :])
        return uri

    def _extract_audio(self, video_uri: str) -> str | None:
        """Extract 16kHz mono WAV from a video via FFmpeg.

        Returns the path to the extracted audio file, or None on failure.
        """
        video_path = self._resolve_uri(video_uri)
        if not os.path.exists(video_path):
            return None

        # Place audio alongside the normalized video
        audio_dir = os.path.dirname(video_path)
        audio_path = os.path.join(audio_dir, "audio.wav")

        # Skip if already extracted
        if os.path.exists(audio_path):
            return audio_path

        cmd = [
            "ffmpeg",
            "-y",
            "-i",
            video_path,
            "-vn",  # no video
            "-acodec",
            "pcm_s16le",  # 16-bit PCM
            "-ar",
            "16000",  # 16 kHz
            "-ac",
            "1",  # mono
            audio_path,
        ]

        try:
            subprocess.run(cmd, capture_output=True, check=True, timeout=300)
        except (subprocess.CalledProcessError, subprocess.TimeoutExpired):
            return None

        return audio_path

    def _build_segments(
        self,
        whisper_result: dict,
        video_id: str,
        language: str | None = None,
    ) -> list[dict]:
        """Convert Whisper output to IO_Rule subtitle_segments format.

        Each segment: {subtitle_id, start_ms, end_ms, text, language, confidence}
        """
        segments: list[dict] = []
        detected_lang = whisper_result.get("language", language or "unknown")

        for i, seg in enumerate(whisper_result.get("segments", [])):
            segments.append(
                {
                    "subtitle_id": f"subtitle_{i + 1:06d}",
                    "video_id": video_id,
                    "start_ms": int(round(seg["start"] * 1000)),
                    "end_ms": int(round(seg["end"] * 1000)),
                    "text": seg["text"].strip(),
                    "language": detected_lang,
                    "confidence": round(seg.get("confidence", 0.0), 4),
                }
            )

        return segments

    @staticmethod
    def _error(code: str, message: str) -> dict:
        """Build an IO_Rule §3 error dict."""
        return {
            "status": "FAILED",
            "error": {"code": code, "message": message, "retryable": False},
        }
