"""Whisper/Doubao adapter — speech-to-text via Doubao (豆包) ASR API.

Replaces local Whisper model with Doubao cloud API.
Follows IO_Rule §4.2 contract.

API key: set via DOUBAO_ASR_API_KEY env var or core.config.Settings.
"""

from __future__ import annotations

import os
import subprocess
import time

from models.base.adapter import BaseModelAdapter
from models.whisper.providers.doubao_asr import DoubaoASRProvider


class WhisperAdapter(BaseModelAdapter):
    """Speech-to-text adapter using Doubao ASR API.

    Extracts audio from normalized video, sends to Doubao cloud API,
    and returns timed subtitle segments per IO_Rule §4.2.
    """

    name = "whisper"
    version = "1.0.0"

    def __init__(self) -> None:
        self._provider: DoubaoASRProvider | None = None
        self._loaded = False
        self._last_segments: list[dict] = []

    # ------------------------------------------------------------------
    # BaseModelAdapter interface
    # ------------------------------------------------------------------

    def load(self, api_key: str | None = None) -> None:
        if self._loaded:
            return
        key = api_key or self._resolve_api_key()
        if not key:
            raise RuntimeError(
                "DOUBAO_ASR_API_KEY not set. "
                "Set it via env var or core.config.Settings.doubao_asr_api_key."
            )
        self._provider = DoubaoASRProvider(api_key=key)
        self._loaded = True

    def unload(self) -> None:
        self._provider = None
        self._loaded = False

    def predict(self, model_input: dict) -> dict:
        """Run transcription via Doubao ASR API.

        IO_Rule §1 input shell. Accepts audio_uri or video_uri.
        Returns IO_Rule §2 output with subtitle_segments.
        """
        if not self._loaded:
            self.load()

        task_id = model_input.get("task_id", "unknown")
        video_id = model_input.get("video_id", "unknown")
        params = model_input.get("parameters", {})

        # Resolve audio
        audio_input = model_input.get("input", {})
        audio_uri = audio_input.get("audio_uri")
        video_uri = audio_input.get("video_uri")

        audio_path: str | None = None
        if audio_uri:
            audio_path = self._resolve_uri(audio_uri)
        elif video_uri:
            audio_path = self._extract_audio(video_uri)
            if audio_path is None:
                return self._error("AUDIO_EXTRACTION_FAILED", "FFmpeg audio extraction failed.")
        else:
            return self._error("NO_AUDIO_INPUT", "Provide audio_uri or video_uri.")

        assert audio_path is not None  # mypy guard
        if not os.path.exists(audio_path):
            return self._error("AUDIO_NOT_FOUND", f"Audio file not found: {audio_path}")

        # Transcribe
        if self._provider is None:
            return self._error("MODEL_NOT_LOADED", "Provider not initialized")
        try:
            t0 = time.monotonic()
            result = self._provider.transcribe(
                audio_path,
                language=params.get("language"),
            )
            runtime_ms = int((time.monotonic() - t0) * 1000)
        except Exception as e:
            return self._error("TRANSCRIPTION_FAILED", str(e))

        # Build segments
        segments = self._build_segments(result, video_id, params.get("language"))

        return {
            "task_id": task_id,
            "video_id": video_id,
            "status": "SUCCEEDED",
            "artifacts": {"subtitle_segments": segments},
            "metrics": {
                "segment_count": len(segments),
                "runtime_ms": runtime_ms,
                "language": result.get("language", params.get("language", "unknown")),
            },
        }

    def health_check(self) -> bool:
        return self._provider is not None and self._provider.health_check()

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    @staticmethod
    def _resolve_api_key() -> str:
        try:
            from core.config import get_settings

            k = get_settings().doubao_asr_api_key
            if k:
                return k
        except Exception:
            pass
        return (
            os.getenv("SPEECH_API_KEY", "")
            or os.getenv("ARK_API_KEY", "")
            or os.getenv("DOUBAO_ASR_API_KEY", "")
        )

    @staticmethod
    def _resolve_uri(uri: str) -> str:
        storage_root = os.getenv("STORAGE_ROOT", "./data")
        prefix = "storage://"
        if uri.startswith(prefix):
            return os.path.join(storage_root, uri[len(prefix) :])
        return uri

    def _extract_audio(self, video_uri: str) -> str | None:
        video_path = self._resolve_uri(video_uri)
        if not os.path.exists(video_path):
            return None
        audio_dir = os.path.dirname(video_path)
        audio_path = os.path.join(audio_dir, "audio.wav")
        if os.path.exists(audio_path):
            return audio_path
        cmd = [
            "ffmpeg",
            "-y",
            "-i",
            video_path,
            "-vn",
            "-acodec",
            "pcm_s16le",
            "-ar",
            "16000",
            "-ac",
            "1",
            audio_path,
        ]
        try:
            subprocess.run(cmd, capture_output=True, check=True, timeout=300)
        except (subprocess.CalledProcessError, subprocess.TimeoutExpired):
            return None
        return audio_path

    def _build_segments(self, api_result: dict, video_id: str, language: str | None) -> list[dict]:
        """Convert API response to IO_Rule subtitle_segments.

        Handles both native ByteDance format (result[0].utterances)
        and OpenAI-compatible format (segments).
        """
        detected_lang = api_result.get("language", language or "unknown")

        # --- ByteDance native format: result[0].utterances ---
        result_list = api_result.get("result", [])
        if result_list:
            r0 = result_list[0] if isinstance(result_list, list) else result_list
            utterances = r0.get("utterances", [])
            if utterances:
                segments: list[dict] = []
                for i, u in enumerate(utterances):
                    segments.append(
                        {
                            "subtitle_id": f"subtitle_{i + 1:06d}",
                            "video_id": video_id,
                            "start_ms": int(u.get("start_time", 0)),
                            "end_ms": int(u.get("end_time", 0)),
                            "text": u.get("text", "").strip(),
                            "language": detected_lang,
                            "confidence": round(u.get("confidence", 0.0), 4),
                        }
                    )
                return segments
            # No utterances — use full text as single segment
            text = r0.get("text", "")
            if text.strip():
                return [
                    {
                        "subtitle_id": "subtitle_000001",
                        "video_id": video_id,
                        "start_ms": 0,
                        "end_ms": 0,
                        "text": text.strip(),
                        "language": detected_lang,
                        "confidence": 0.0,
                    }
                ]

        # --- OpenAI-compatible format: text + segments ---
        raw_segments = api_result.get("segments", [])
        if raw_segments:
            segments = []
            for i, seg in enumerate(raw_segments):
                segments.append(
                    {
                        "subtitle_id": f"subtitle_{i + 1:06d}",
                        "video_id": video_id,
                        "start_ms": int(round(seg.get("start", seg.get("begin", 0)) * 1000)),
                        "end_ms": int(round(seg.get("end", 0) * 1000)),
                        "text": seg.get("text", "").strip(),
                        "language": detected_lang,
                        "confidence": round(seg.get("confidence", 0.0), 4),
                    }
                )
            return segments

        # --- Fallback: single segment from top-level text ---
        text = api_result.get("text", "")
        if text.strip():
            return [
                {
                    "subtitle_id": "subtitle_000001",
                    "video_id": video_id,
                    "start_ms": 0,
                    "end_ms": 0,
                    "text": text.strip(),
                    "language": detected_lang,
                    "confidence": 0.0,
                }
            ]
        return []

    @staticmethod
    def _error(code: str, message: str) -> dict:
        return {
            "status": "FAILED",
            "error": {"code": code, "message": message, "retryable": False},
        }
