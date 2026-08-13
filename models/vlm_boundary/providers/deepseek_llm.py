"""DeepSeek LLM provider — same API platform as Qwen."""

import json
import logging
import time

import requests

from models.vlm_boundary.providers.base import BaseProvider

logger = logging.getLogger(__name__)


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
    ):
        self.api_key = api_key
        self.model = model
        self.base_url = base_url
        self.max_tokens = max_tokens
        self.temperature = temperature
        self.timeout = timeout
        self.max_attempts = max(1, min(5, max_attempts))
        self.retry_delay_s = max(0.0, retry_delay_s)

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
        for attempt in range(1, self.max_attempts + 1):
            try:
                resp = requests.post(self.base_url, headers=headers, json=payload, timeout=t)
                if resp.status_code == 200:
                    elapsed = int((time.monotonic() - started) * 1000)
                    content = resp.json()["choices"][0]["message"]["content"]
                    return _parse_json(content, elapsed)
                if resp.status_code != 429 and resp.status_code < 500:
                    raise RuntimeError(f"DeepSeek API {resp.status_code}: {resp.text[:500]}")
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

        raise RuntimeError(
            f"DeepSeek request failed after {self.max_attempts} attempts: {last_error}"
        ) from last_error

    def health_check(self) -> bool:
        try:
            return (
                requests.get(
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
            response = requests.get(
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
