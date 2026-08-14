"""DeepSeek LLM provider — same API platform as Qwen."""

import json
import logging
import time

import requests
from requests.adapters import HTTPAdapter

from models.vlm_boundary.providers.base import BaseProvider

logger = logging.getLogger(__name__)


class DeepSeekRequestError(RuntimeError):
    """Provider failure carrying retry/429 telemetry for adaptive scheduling."""

    def __init__(self, message: str, telemetry: dict) -> None:
        super().__init__(message)
        self.telemetry = telemetry


class DeepSeekLLMProvider(BaseProvider):
    def __init__(
        self,
        api_key: str,
        model: str = "deepseek-v4-flash",
        base_url: str = "https://api.modelarts-maas.com/v1/chat/completions",
        max_tokens: int = 8192,
        temperature: float = 0.3,
        timeout: int = 180,
        max_attempts: int = 3,
        retry_delay_s: float = 1.0,
        pool_size: int = 8,
    ):
        self.api_key = api_key
        self.model = model
        self.base_url = base_url
        self.max_tokens = max_tokens
        self.temperature = temperature
        self.timeout = timeout
        self.max_attempts = max(1, min(5, max_attempts))
        self.retry_delay_s = max(0.0, retry_delay_s)
        self.session = requests.Session()
        self.session.mount(
            "https://",
            HTTPAdapter(
                pool_connections=max(1, pool_size),
                pool_maxsize=max(1, pool_size),
                max_retries=0,
                pool_block=True,
            ),
        )

    def send(self, messages: list[dict], **kwargs) -> dict:
        headers = {"Content-Type": "application/json", "Authorization": f"Bearer {self.api_key}"}
        payload = {
            "model": self.model,
            "messages": messages,
            "max_tokens": kwargs.get("max_tokens", self.max_tokens),
            "temperature": kwargs.get("temperature", self.temperature),
        }
        t = kwargs.get("timeout", self.timeout)
        started = time.monotonic()
        last_error: Exception | None = None
        status_codes: list[int] = []
        rate_limited = False
        for attempt in range(1, self.max_attempts + 1):
            try:
                resp = self.session.post(self.base_url, headers=headers, json=payload, timeout=t)
                status_codes.append(resp.status_code)
                if resp.status_code == 200:
                    elapsed = int((time.monotonic() - started) * 1000)
                    content = resp.json()["choices"][0]["message"]["content"]
                    parsed = _parse_json(content, elapsed)
                    parsed["telemetry"] = {
                        "elapsed_ms": elapsed,
                        "attempts": attempt,
                        "retry_count": attempt - 1,
                        "status_codes": status_codes,
                        "rate_limited": rate_limited,
                    }
                    return parsed
                if resp.status_code != 429 and resp.status_code < 500:
                    elapsed = int((time.monotonic() - started) * 1000)
                    raise DeepSeekRequestError(
                        f"DeepSeek API {resp.status_code}: {resp.text[:500]}",
                        {
                            "elapsed_ms": elapsed,
                            "attempts": attempt,
                            "retry_count": attempt - 1,
                            "status_codes": status_codes,
                            "rate_limited": rate_limited,
                        },
                    )
                rate_limited = rate_limited or resp.status_code == 429
                last_error = RuntimeError(
                    f"DeepSeek retryable API {resp.status_code}: {resp.text[:500]}"
                )
            except (requests.Timeout, requests.ConnectionError) as exc:
                last_error = exc

            if attempt < self.max_attempts:
                logger.warning(
                    "deepseek_request_retry",
                    extra={"attempt": attempt, "max_attempts": self.max_attempts},
                )
                time.sleep(self.retry_delay_s * attempt)

        elapsed = int((time.monotonic() - started) * 1000)
        raise DeepSeekRequestError(
            f"DeepSeek request failed after {self.max_attempts} attempts: {last_error}",
            {
                "elapsed_ms": elapsed,
                "attempts": self.max_attempts,
                "retry_count": self.max_attempts - 1,
                "status_codes": status_codes,
                "rate_limited": rate_limited,
            },
        ) from last_error

    def health_check(self) -> bool:
        try:
            return (
                self.session.get(
                    self.base_url.replace("/chat/completions", "/models"),
                    headers={"Authorization": f"Bearer {self.api_key}"},
                    timeout=10,
                ).status_code
                == 200
            )
        except Exception:
            return False

    def configured_model_available(self) -> bool:
        """Validate credentials and the configured inference model together."""
        try:
            response = self.session.get(
                self.base_url.replace("/chat/completions", "/models"),
                headers={"Authorization": f"Bearer {self.api_key}"},
                timeout=10,
            )
            if response.status_code != 200:
                return False
            model_ids = {str(item.get("id", "")) for item in response.json().get("data", [])}
            return self.model in model_ids
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
            return {"data": json.loads(text[s:e].strip()), "raw": text, "elapsed_ms": elapsed}
        except json.JSONDecodeError:
            pass
    elif "```" in text:
        s = text.index("```") + 3
        e = text.index("```", s)
        try:
            return {"data": json.loads(text[s:e].strip()), "raw": text, "elapsed_ms": elapsed}
        except json.JSONDecodeError:
            pass
    return {"data": {"raw_text": text}, "raw": text, "elapsed_ms": elapsed}
