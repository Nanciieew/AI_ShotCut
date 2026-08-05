"""DeepSeek LLM provider — same API platform as Qwen."""

import json, time
import requests
from models.vlm_boundary.providers.base import BaseProvider


class DeepSeekLLMProvider(BaseProvider):
    def __init__(
        self,
        api_key: str,
        model: str = "deepseek-v4-flash-DKZcog",
        base_url: str = "https://api.modelarts-maas.com/v1/chat/completions",
        max_tokens: int = 8192,
        temperature: float = 0.3,
        timeout: int = 180,
    ):
        self.api_key = api_key
        self.model = model
        self.base_url = base_url
        self.max_tokens = max_tokens
        self.temperature = temperature
        self.timeout = timeout

    def send(self, messages: list[dict], **kwargs) -> dict:
        headers = {"Content-Type": "application/json", "Authorization": f"Bearer {self.api_key}"}
        payload = {
            "model": self.model,
            "messages": messages,
            "max_tokens": kwargs.get("max_tokens", self.max_tokens),
            "temperature": kwargs.get("temperature", self.temperature),
        }
        t0 = time.monotonic()
        t = kwargs.get("timeout", self.timeout)
        resp = requests.post(self.base_url, headers=headers, data=json.dumps(payload), timeout=t)
        elapsed = int((time.monotonic() - t0) * 1000)
        if resp.status_code != 200:
            raise RuntimeError(f"DeepSeek API {resp.status_code}: {resp.text[:500]}")
        content = resp.json()["choices"][0]["message"]["content"]
        return _parse_json(content, elapsed)

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
