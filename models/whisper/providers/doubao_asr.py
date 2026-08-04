"""Doubao (豆包) ASR provider — ByteDance OpenSpeech native API.

Endpoint: openspeech.bytedance.com/api/v3/auc/bigmodel/recognize/flash
Auth: X-Api-Key header with speech API key.
"""

from __future__ import annotations

import base64
import os
import time
import uuid

import requests


class DoubaoASRProvider:
    """Doubao speech recognition via ByteDance OpenSpeech.

    Uses the native bigmodel ASR API (not OpenAI-compatible).
    """

    def __init__(
        self,
        api_key: str,
        model: str = "bigmodel",
        base_url: str = "https://openspeech.bytedance.com/api/v3/auc/bigmodel/recognize/flash",
        resource_id: str = "volc.bigasr.auc_turbo",
        timeout: int = 300,
    ) -> None:
        # Extract UUID from "api-key-xxx:uuid" format if present
        self.api_key = api_key.split(":")[-1] if ":" in api_key else api_key
        self.model = model
        self.base_url = base_url
        self.resource_id = resource_id
        self.timeout = timeout

    def transcribe(
        self,
        audio_path: str,
        language: str | None = None,
    ) -> dict:
        """Send audio to Doubao ASR and return transcription result.

        Parameters
        ----------
        audio_path : str
            Path to audio file (WAV, MP3, etc.). Max ~100MB.
        language : str | None
            Language hint (ignored by bigmodel — auto-detected).

        Returns
        -------
        dict
            Parsed API response with `text` and optional `result` segments.
        """
        with open(audio_path, "rb") as f:
            audio_b64 = base64.b64encode(f.read()).decode("utf-8")

        headers = {
            "X-Api-Key": self.api_key,
            "X-Api-Resource-Id": self.resource_id,
            "X-Api-Request-Id": str(uuid.uuid4()),
            "X-Api-Sequence": "-1",
            "Content-Type": "application/json",
        }

        payload = {
            "user": {"uid": "ai-shotcut"},
            "audio": {"data": audio_b64},
            "request": {"model_name": self.model},
        }

        t0 = time.monotonic()
        resp = requests.post(
            self.base_url,
            headers=headers,
            json=payload,
            timeout=self.timeout,
        )
        elapsed_ms = int((time.monotonic() - t0) * 1000)

        if resp.status_code != 200:
            raise RuntimeError(
                f"Doubao ASR {resp.status_code}: {resp.text[:500]}"
            )

        result = resp.json()
        result["_elapsed_ms"] = elapsed_ms
        return result

    def health_check(self) -> bool:
        """Check API connectivity by probing the base host."""
        try:
            resp = requests.get(
                "https://openspeech.bytedance.com",
                timeout=10,
            )
            return resp.status_code < 500
        except Exception:
            return False
