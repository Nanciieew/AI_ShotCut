"""LLM Plot Event Adapter — DeepSeek. Text-only (subtitles -> plot scores)."""

import os
from typing import Any

from models.base.adapter import BaseModelAdapter
from models.vlm_boundary.providers.deepseek_llm import DeepSeekLLMProvider


class PlotEventAdapter(BaseModelAdapter):
    name = "plot_event"
    version = "0.1.0"

    def __init__(self):
        self._provider = None
        self._loaded = False
        self._last_result = {}

    def load(self, api_key: str | None = None) -> None:
        if self._loaded:
            return
        key = api_key or self._resolve_api_key()
        if not key:
            raise RuntimeError("QWEN_VL_API_KEY not set")
        self._provider = DeepSeekLLMProvider(api_key=key)
        self._loaded = True

    def unload(self):
        self._provider = None
        self._loaded = False

    def health_check(self) -> bool:
        return self._provider is not None and self._provider.health_check()

    @staticmethod
    def _resolve_api_key() -> str:
        try:
            from core.config import get_settings

            k = get_settings().qwen_vl_api_key
            if k:
                return k
        except Exception:
            pass
        return os.getenv("QWEN_VL_API_KEY", "")

    def predict(self, model_input: dict[str, Any]) -> dict[str, Any]:
        # Stub — plot scoring not yet implemented in Phase 1
        sv = model_input.get("schema_version", "1.0")
        return {
            "schema_version": sv,
            "task_id": model_input["task_id"],
            "video_id": model_input["video_id"],
            "status": "SUCCEEDED",
            "model": {"name": "plot_event", "version": "0.1.0"},
            "artifacts": {},
            "metrics": {"note": "plot_event stub — Phase 2"},
            "error": None,
        }
