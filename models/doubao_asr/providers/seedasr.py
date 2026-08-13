"""SeedASR Provider — Volcano Engine OpenSpeech async ASR API.

Flow: Submit task → Poll until DONE → Extract utterances
Endpoint: openspeech.bytedance.com/api/v3/auc/bigmodel
Resource: volc.seedasr.auc
"""

from __future__ import annotations

import logging
import os
import time
import uuid
from typing import Any

import requests

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------

SEEDASR_HOST = "https://openspeech.bytedance.com"
SEEDASR_SUBMIT = f"{SEEDASR_HOST}/api/v3/auc/bigmodel/submit"
SEEDASR_QUERY = f"{SEEDASR_HOST}/api/v3/auc/bigmodel/query"
SEEDASR_RESOURCE_ID = "volc.seedasr.auc"
SEEDASR_POLL_INTERVAL = 2  # seconds
SEEDASR_MAX_POLLS = 600  # 20 min


class SeedASRProvider:
    """Doubao SeedASR via Volcano OpenSpeech async API.

    Uses old-console auth: X-Api-App-Key + X-Api-Access-Key.
    """

    def __init__(
        self,
        app_id: str | None = None,
        access_token: str | None = None,
        host: str | None = None,
        poll_interval: float | None = None,
    ) -> None:
        self.app_id = app_id or SeedASRProvider._resolve_app_id()
        self.access_token = access_token or SeedASRProvider._resolve_access_token()
        self.host: str = host or os.getenv("VOLC_HOST") or SEEDASR_HOST
        self.submit_url = f"{self.host}/api/v3/auc/bigmodel/submit"
        self.query_url = f"{self.host}/api/v3/auc/bigmodel/query"
        self.poll_interval = poll_interval or float(
            os.getenv("POLL_INTERVAL", str(SEEDASR_POLL_INTERVAL))
        )

        if not self.app_id or not self.access_token:
            raise RuntimeError(
                "VOLC_APP_ID and VOLC_ACCESS_TOKEN must be set in .env "
                "or passed to SeedASRProvider(app_id=..., access_token=...)"
            )

    # ------------------------------------------------------------------
    # Key resolution (Settings → env fallback)
    # ------------------------------------------------------------------

    @staticmethod
    def _resolve_app_id() -> str:
        try:
            from core.config import get_settings

            k = get_settings().volc_app_id
            if k:
                return k
        except Exception:
            pass
        return os.getenv("VOLC_APP_ID", "")

    @staticmethod
    def _resolve_access_token() -> str:
        try:
            from core.config import get_settings

            k = get_settings().volc_access_token
            if k:
                return k
        except Exception:
            pass
        return os.getenv("VOLC_ACCESS_TOKEN", "")

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def transcribe(
        self,
        audio_url: str,
        audio_format: str = "wav",
        language: str | None = "zh-CN",
    ) -> dict[str, Any]:
        """Submit audio and poll until done.

        Returns raw API response with result.utterances[].
        """
        provider_request_id = self._submit(audio_url, audio_format, language)
        return self._poll(provider_request_id)

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    def _submit(self, audio_url: str, audio_format: str, language: str | None) -> str:
        """Submit async transcription task. Returns provider_request_id."""
        provider_request_id = uuid.uuid4().hex
        headers = {
            "X-Api-App-Key": self.app_id,
            "X-Api-Access-Key": self.access_token,
            "X-Api-Resource-Id": SEEDASR_RESOURCE_ID,
            "X-Api-Request-Id": provider_request_id,
            "X-Api-Sequence": "-1",
            "Content-Type": "application/json",
        }
        payload: dict[str, Any] = {
            "user": {"uid": "ai-shotcut"},
            "audio": {
                "url": audio_url,
                "format": audio_format,
            },
            "request": {
                "model_name": "bigmodel",
                "show_utterances": True,
                "enable_itn": True,
                "enable_punc": True,
            },
        }
        if language:
            payload["audio"]["language"] = language

        resp = requests.post(self.submit_url, headers=headers, json=payload, timeout=60)
        status_code = resp.headers.get("X-Api-Status-Code", "")
        if status_code != "20000000":
            msg = resp.headers.get("X-Api-Message", "")
            raise RuntimeError(
                f"SeedASR submit failed: [{status_code}] {msg}. Body: {resp.text[:500]}"
            )

        logger.info("SeedASR submitted: provider_request_id=%s", provider_request_id)
        return provider_request_id

    def _poll(self, provider_request_id: str) -> dict[str, Any]:
        """Poll until DONE. Returns parsed JSON response."""
        for i in range(SEEDASR_MAX_POLLS):
            time.sleep(self.poll_interval)

            headers = {
                "X-Api-App-Key": self.app_id,
                "X-Api-Access-Key": self.access_token,
                "X-Api-Resource-Id": SEEDASR_RESOURCE_ID,
                "X-Api-Request-Id": provider_request_id,
                "Content-Type": "application/json",
            }

            resp = requests.post(self.query_url, headers=headers, json={}, timeout=30)
            status_code = resp.headers.get("X-Api-Status-Code", "")

            if status_code == "20000000":
                data = resp.json()
                elapsed = (i + 1) * self.poll_interval
                logger.info("SeedASR done after %.0fs", elapsed)
                return data

            if status_code in ("20000001", "20000002"):
                if i % 10 == 0:
                    logger.debug("SeedASR polling... (%.0fs)", (i + 1) * self.poll_interval)
                continue

            if status_code == "20000003":
                logger.info("SeedASR: silent audio, returning empty")
                return {"result": {"text": "", "utterances": []}}

            # Error
            msg = resp.headers.get("X-Api-Message", resp.text[:200])
            raise RuntimeError(f"SeedASR poll error [{status_code}]: {msg}")

        raise TimeoutError(
            f"SeedASR provider_request_id={provider_request_id} "
            f"timed out after {SEEDASR_MAX_POLLS * self.poll_interval}s"
        )

    def health_check(self) -> bool:
        """Verify credentials and connectivity."""
        try:
            resp = requests.get(self.host, timeout=10)
            return resp.status_code < 500
        except Exception:
            return False
