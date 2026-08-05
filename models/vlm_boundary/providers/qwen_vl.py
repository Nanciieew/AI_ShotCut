"""Qwen2.5-VL provider — requests + base64 JPEG."""

import base64, json, time
import requests
from models.vlm_boundary.providers.base import BaseProvider

JPEG_PREFIX = "data:image/jpeg;base64,"


def encode_image_jpeg(path: str) -> str:
    with open(path, "rb") as f:
        return JPEG_PREFIX + base64.b64encode(f.read()).decode("utf-8")


class QwenVLProvider(BaseProvider):
    def __init__(
        self,
        api_key: str,
        model: str = "qwen2.5-vl-72b-KFF1r3",
        base_url: str = "https://api.modelarts-maas.com/v1/chat/completions",
        max_tokens: int = 4096,
        temperature: float = 0.1,
        timeout: int = 120,
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
        resp = requests.post(
            self.base_url, headers=headers, data=json.dumps(payload), timeout=self.timeout
        )
        elapsed = int((time.monotonic() - t0) * 1000)
        if resp.status_code != 200:
            raise RuntimeError(f"Qwen API {resp.status_code}: {resp.text[:500]}")
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
