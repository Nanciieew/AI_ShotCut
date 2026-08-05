"""VLM Scene Boundary Adapter — Qwen2.5-VL. Location + character scoring."""

import json
import os
import time
from typing import Any

from models.base.adapter import BaseModelAdapter
from models.vlm_boundary.prompts import LOCATION_CHARACTER_BATCH_TEMPLATE, LOCATION_CHARACTER_SYSTEM
from models.vlm_boundary.providers.qwen_vl import QwenVLProvider, encode_image_jpeg

BATCH_SIZE = 200


class VLMSceneBoundaryAdapter(BaseModelAdapter):
    name = "vlm_scene_boundary"
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
        self._provider = QwenVLProvider(api_key=key)
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
        if not self._loaded:
            self.load()
        sv = model_input.get("schema_version", "1.0")
        tid = model_input["task_id"]
        vid = model_input["video_id"]
        shots_uri = model_input["input"]["shots_uri"]
        kf_dir = model_input["input"]["keyframes_dir"]
        bs = model_input.get("parameters", {}).get("batch_size", BATCH_SIZE)
        try:
            sp = self._r(shots_uri)
            with open(sp) as f:
                shots = json.load(f).get("shots", [])
            n = len(shots)
            if n < 2:
                return self._e(tid, vid, sv, "TOO_FEW_SHOTS", f"Need>=2, got {n}", False)
            kb = self._d(kf_dir)
            bounds = []
            for i in range(n - 1):
                ef = f"{kb}/{shots[i]['shot_id']}_003_004.jpg"
                sf = f"{kb}/{shots[i + 1]['shot_id']}_001_004.jpg"
                if not os.path.exists(ef):
                    ef = f"{kb}/shot_{shots[i]['index']:06d}_img_3.jpg"
                if not os.path.exists(sf):
                    sf = f"{kb}/shot_{shots[i + 1]['index']:06d}_img_1.jpg"
                bounds.append({"shot_id": shots[i]["shot_id"], "end_frame": ef, "start_frame": sf})

            # Auto-detect batch_size from image resolution
            if bs == BATCH_SIZE:  # user didn't override — auto-detect
                try:
                    from PIL import Image

                    sample = bounds[0]["end_frame"]
                    if os.path.exists(sample):
                        w, _ = Image.open(sample).size
                        if w <= 320:
                            bs = 200
                        elif w <= 672:
                            bs = 3
                        else:
                            bs = 2
                except Exception:
                    pass

            t0 = time.monotonic()
            all_s = []
            for bs0 in range(0, len(bounds), bs):
                batch = bounds[bs0 : bs0 + bs]
                uc = [
                    {
                        "type": "text",
                        "text": LOCATION_CHARACTER_BATCH_TEMPLATE.format(
                            batch_size=len(batch), shot_ids=", ".join(b["shot_id"] for b in batch)
                        ),
                    }
                ]
                for b in batch:
                    for fp in [b["end_frame"], b["start_frame"]]:
                        if os.path.exists(fp):
                            uc.append(
                                {
                                    "type": "image_url",
                                    "image_url": {"url": encode_image_jpeg(fp)},  # type: ignore[dict-item]
                                }
                            )
                resp = self._provider.send(
                    [
                        {"role": "system", "content": LOCATION_CHARACTER_SYSTEM},
                        {"role": "user", "content": uc},
                    ]
                )
                all_s.extend(resp.get("data", {}).get("scores", []))
            rt = int((time.monotonic() - t0) * 1000)
            art = f"projects/{vid[:8]}/videos/{vid}/artifacts/vlm_boundary/{self.version}/location_character_scores.json"
            self._last_result = {"video_id": vid, "scores": all_s}
            return self._ok(
                tid, vid, sv, "location_character_scores", f"storage://{art}", len(all_s), rt
            )
        except Exception as e:
            return self._e(tid, vid, sv, "VLM_INFERENCE_FAILED", str(e), True)

    @staticmethod
    def _r(u):
        p = "storage://"
        return (
            os.path.join(os.getenv("STORAGE_ROOT", "./data"), u[len(p) :]) if u.startswith(p) else u
        )

    @staticmethod
    def _d(u):
        return VLMSceneBoundaryAdapter._r(u)

    @staticmethod
    def _ok(t, v, s, k, u, c, m):
        return {
            "schema_version": s,
            "task_id": t,
            "video_id": v,
            "status": "SUCCEEDED",
            "model": {"name": "vlm_scene_boundary", "version": "0.1.0"},
            "artifacts": {k: u},
            "metrics": {"score_count": c, "runtime_ms": m},
            "error": None,
        }

    @staticmethod
    def _e(t, v, s, c, m, r):
        return {
            "schema_version": s,
            "task_id": t,
            "video_id": v,
            "status": "FAILED",
            "model": {"name": "vlm_scene_boundary", "version": "0.1.0"},
            "artifacts": {},
            "metrics": {},
            "error": {"code": c, "message": m, "retryable": r},
        }
