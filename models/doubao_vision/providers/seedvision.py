"""SeedVision Provider — Volcano Ark Doubao-Seed-1.6-vision chat completions.

OpenAI-compatible /v3/chat/completions endpoint.
Auth: Authorization: Bearer {api_key} (new console format).
"""

from __future__ import annotations

import json
import logging
import os
import time

import requests
from requests.adapters import HTTPAdapter

logger = logging.getLogger(__name__)

ARK_VISION_BASE = "https://ark.cn-beijing.volces.com/api/v3/chat/completions"
DEFAULT_MODEL = "ep-20260812100758-6b9d4"
DEFAULT_MAX_TOKENS = 4096
DEFAULT_TEMPERATURE = 0.1


class SeedVisionAPIError(RuntimeError):
    """Structured provider error so Workflow retry policy is not guessed."""

    def __init__(self, message: str, *, retryable: bool) -> None:
        super().__init__(message)
        self.retryable = retryable


class SeedVisionProvider:
    """Doubao-Seed-1.6-vision via Volcano Ark OpenAI-compatible API."""

    def __init__(
        self,
        api_key: str | None = None,
        model: str | None = None,
        base_url: str | None = None,
        max_tokens: int = DEFAULT_MAX_TOKENS,
        temperature: float = DEFAULT_TEMPERATURE,
        timeout: int = 120,
        max_attempts: int = 3,
        retry_backoff_seconds: float = 1.0,
        session: requests.Session | None = None,
    ) -> None:
        self.api_key = api_key or SeedVisionProvider._resolve_api_key()
        self.model = model or DEFAULT_MODEL
        self.base_url = base_url or ARK_VISION_BASE
        self.max_tokens = max_tokens
        self.temperature = temperature
        self.timeout = timeout
        self.max_attempts = max(1, max_attempts)
        self.retry_backoff_seconds = max(0.0, retry_backoff_seconds)
        self.session = session or requests.Session()
        adapter = HTTPAdapter(pool_connections=4, pool_maxsize=4)
        self.session.mount("https://", adapter)
        self.session.mount("http://", adapter)

        if not self.api_key:
            raise RuntimeError(
                "VOLC_VISION_API_KEY must be set in .env "
                "or passed to SeedVisionProvider(api_key=...)"
            )

    # ------------------------------------------------------------------
    # Key resolution (Settings → env fallback)
    # ------------------------------------------------------------------

    @staticmethod
    def _resolve_api_key() -> str:
        try:
            from core.config import get_settings

            k = get_settings().volc_vision_api_key
            if k:
                return k
        except Exception:
            pass
        return os.getenv("VOLC_VISION_API_KEY", "")

    # ------------------------------------------------------------------
    # Public
    # ------------------------------------------------------------------

    def send(self, messages: list[dict], **kwargs) -> dict:
        """Send chat completion request.

        Returns: {"data": parsed_response, "raw": raw_text, "elapsed_ms": int}
        """
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.api_key}",
        }
        payload = {
            "model": self.model,
            "messages": messages,
            "max_tokens": kwargs.get("max_tokens", self.max_tokens),
            "temperature": kwargs.get("temperature", self.temperature),
        }

        t0 = time.monotonic()
        resp = None
        for attempt in range(1, self.max_attempts + 1):
            attempt_started = time.monotonic()
            try:
                resp = self.session.post(
                    self.base_url,
                    headers=headers,
                    json=payload,
                    timeout=(10, self.timeout),
                )
            except (requests.Timeout, requests.ConnectionError) as exc:
                attempt_elapsed = int((time.monotonic() - attempt_started) * 1000)
                logger.warning(
                    "seedvision_request_retry",
                    extra={
                        "attempt": attempt,
                        "max_attempts": self.max_attempts,
                        "elapsed_ms": attempt_elapsed,
                        "error_type": type(exc).__name__,
                    },
                )
                if attempt >= self.max_attempts:
                    raise SeedVisionAPIError(
                        f"SeedVision network error after {attempt} attempts: {exc}",
                        retryable=True,
                    ) from exc
                self._backoff(attempt)
                continue

            retryable_status = resp.status_code == 429 or resp.status_code >= 500
            if resp.status_code == 200:
                break
            if retryable_status and attempt < self.max_attempts:
                logger.warning(
                    "seedvision_http_retry",
                    extra={
                        "attempt": attempt,
                        "max_attempts": self.max_attempts,
                        "status_code": resp.status_code,
                        "elapsed_ms": int((time.monotonic() - attempt_started) * 1000),
                    },
                )
                self._backoff(attempt, resp.headers.get("Retry-After"))
                continue
            raise SeedVisionAPIError(
                f"SeedVision API {resp.status_code}: {resp.text[:500]}",
                retryable=retryable_status,
            )

        if resp is None:  # defensive; the loop either returns a response or raises
            raise SeedVisionAPIError("SeedVision request produced no response", retryable=True)
        elapsed = int((time.monotonic() - t0) * 1000)

        content = resp.json()["choices"][0]["message"]["content"]
        return _parse_json(content, elapsed)

    def _backoff(self, attempt: int, retry_after: str | None = None) -> None:
        delay = self.retry_backoff_seconds * (2 ** (attempt - 1))
        if retry_after:
            try:
                delay = max(delay, min(float(retry_after), 30.0))
            except ValueError:
                pass
        if delay:
            time.sleep(delay)

    def close(self) -> None:
        self.session.close()

    def health_check(self) -> bool:
        try:
            resp = self.session.get(
                "https://ark.cn-beijing.volces.com/api/v3/models",
                headers={"Authorization": f"Bearer {self.api_key}"},
                timeout=10,
            )
            return resp.status_code == 200
        except Exception:
            return False


def _parse_json(text: str, elapsed: int) -> dict:
    try:
        return {"data": json.loads(text), "raw": text, "elapsed_ms": elapsed}
    except json.JSONDecodeError:
        pass
    if "```json" in text:
        s = text.index("```json") + 7
        e = text.index("```", s)
        try:
            return {
                "data": json.loads(text[s:e].strip()),
                "raw": text,
                "elapsed_ms": elapsed,
            }
        except json.JSONDecodeError:
            pass
    elif "```" in text:
        s = text.index("```") + 3
        e = text.index("```", s)
        try:
            return {
                "data": json.loads(text[s:e].strip()),
                "raw": text,
                "elapsed_ms": elapsed,
            }
        except json.JSONDecodeError:
            pass
    return {"data": {"raw_text": text}, "raw": text, "elapsed_ms": elapsed}
