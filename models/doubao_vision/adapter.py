"""Doubao Vision Adapter — Doubao-Seed-1.6-vision for scene boundary scoring.

Replaces Qwen VL (VLMSceneBoundaryAdapter). Uses Volcano Ark OpenAI-compatible
/v3/chat/completions endpoint with the same keyframe pair scoring logic.

IO_Rule §4.3: shots_uri + keyframes_uri → location_character_scores
"""

from __future__ import annotations

import json
import logging
import os
import time
from concurrent.futures import ThreadPoolExecutor
from typing import Any

from models.base.adapter import BaseModelAdapter
from models.doubao_vision.providers.seedvision import SeedVisionAPIError, SeedVisionProvider
from models.vlm_boundary.prompts import (
    LOCATION_CHARACTER_BATCH_TEMPLATE,
    LOCATION_CHARACTER_SYSTEM,
)

BATCH_SIZE = 1
MAX_CONCURRENCY = 3
MAX_ATTEMPTS = 2

logger = logging.getLogger(__name__)


def _encode_image(path: str) -> str:
    """Encode the existing JPEG directly, avoiding a much larger PNG payload."""
    import base64

    with open(path, "rb") as image_file:
        encoded = base64.b64encode(image_file.read()).decode("ascii")
    return "data:image/jpeg;base64," + encoded


class DoubaoVisionAdapter(BaseModelAdapter):
    """Doubao-Seed-1.6-vision adapter for location + character boundary scoring."""

    name = "doubao_vision"
    version = "1.0.0"

    def __init__(self) -> None:
        self._provider: SeedVisionProvider | None = None
        self._loaded = False
        self._last_result: dict[str, Any] = {}

    # ------------------------------------------------------------------
    # BaseModelAdapter interface
    # ------------------------------------------------------------------

    def load(self, api_key: str | None = None) -> None:  # noqa: ARG002
        if self._loaded:
            return
        self._provider = SeedVisionProvider(api_key=api_key)
        self._loaded = True

    def unload(self) -> None:
        self._provider = None
        self._loaded = False

    def predict(self, model_input: dict[str, Any]) -> dict[str, Any]:
        if not self._loaded:
            self.load()
        provider = self._provider
        if provider is None:
            return self._e(
                "",
                "",
                "1.0",
                "PROVIDER_NOT_LOADED",
                "Vision provider is not loaded",
                False,
            )

        sv = model_input.get("schema_version", "1.0")
        tid = model_input["task_id"]
        vid = model_input["video_id"]
        shots_uri = model_input["input"]["shots_uri"]
        keyframes_uri = model_input["input"]["keyframes_uri"]
        params = model_input.get("parameters", {})
        # One boundary per request prevents the model from omitting or merging IDs.
        bs = max(1, min(1, int(params.get("batch_size", BATCH_SIZE))))
        concurrency = max(1, min(4, int(params.get("concurrency", MAX_CONCURRENCY))))
        max_attempts = max(1, min(3, int(params.get("max_attempts", MAX_ATTEMPTS))))

        try:
            # Load shots
            sp = self._r(shots_uri)
            with open(sp) as f:
                shots = json.load(f).get("shots", [])
            n = len(shots)
            if n < 2:
                return self._e(tid, vid, sv, "TOO_FEW_SHOTS", f"Need>=2, got {n}", False)

            with open(self._r(keyframes_uri), encoding="utf-8") as file:
                keyframe_summary = json.load(file)
            samples_by_shot = {
                str(item["shot_id"]): {
                    (sample.get("position_num"), sample.get("position_den")): sample.get("uri")
                    for sample in item.get("samples", [])
                    if sample.get("uri")
                }
                for item in keyframe_summary.get("shots", [])
            }

            # Build boundary keyframe pairs from Artifact URIs, not filenames.
            bounds = []
            for i in range(n - 1):
                end_uri = samples_by_shot.get(str(shots[i]["shot_id"]), {}).get((3, 4))
                start_uri = samples_by_shot.get(str(shots[i + 1]["shot_id"]), {}).get((1, 4))
                if not end_uri or not start_uri:
                    raise ValueError(
                        f"Missing keyframe URI for boundary after {shots[i]['shot_id']}"
                    )
                ef = self._r(end_uri)
                sf = self._r(start_uri)
                if not os.path.isfile(ef) or not os.path.isfile(sf):
                    raise FileNotFoundError(
                        f"Keyframe file missing for boundary after {shots[i]['shot_id']}"
                    )
                bounds.append({"shot_id": shots[i]["shot_id"], "end_frame": ef, "start_frame": sf})

            # Score each boundary independently. Requests use a bounded pool, and every
            # response is validated/retried immediately instead of failing after all work.
            t0 = time.monotonic()
            batches = [bounds[start : start + bs] for start in range(0, len(bounds), bs)]

            def score_batch(batch: list[dict]) -> list[dict]:
                expected_ids = [str(item["shot_id"]) for item in batch]
                uc: list[dict[str, Any]] = [
                    {
                        "type": "text",
                        "text": LOCATION_CHARACTER_BATCH_TEMPLATE.format(
                            batch_size=len(batch),
                            shot_ids=", ".join(b["shot_id"] for b in batch),
                        ),
                    }
                ]
                for b in batch:
                    for fp in [b["end_frame"], b["start_frame"]]:
                        if os.path.exists(fp):
                            uc.append(
                                {
                                    "type": "image_url",
                                    "image_url": {"url": _encode_image(fp)},
                                }
                            )

                messages: list[dict[str, Any]] = [
                    {"role": "system", "content": LOCATION_CHARACTER_SYSTEM},
                    {"role": "user", "content": uc},
                ]
                last_problem = "no response"
                for attempt in range(1, max_attempts + 1):
                    resp = provider.send(messages)
                    scores = resp.get("data", {}).get("scores", [])
                    # Batches are intentionally fixed to one boundary. The model's
                    # echoed UUID is untrusted metadata and may contain formatting
                    # drift, so bind the single response to the request-side ID.
                    if isinstance(scores, list) and len(scores) == 1:
                        score = scores[0]
                        if isinstance(score, dict):
                            try:
                                location = float(score["location_change"])
                                character = float(score["character_group_change"])
                            except (KeyError, TypeError, ValueError):
                                pass
                            else:
                                if 0.0 <= location <= 100.0 and 0.0 <= character <= 100.0:
                                    return [
                                        {
                                            **score,
                                            "shot_id": expected_ids[0],
                                            "location_change": location,
                                            "character_group_change": character,
                                        }
                                    ]
                    returned_ids = (
                        [str(item.get("shot_id", "")) for item in scores]
                        if isinstance(scores, list)
                        else []
                    )
                    last_problem = (
                        f"expected_count=1, returned_count="
                        f"{len(scores) if isinstance(scores, list) else 'invalid'}, "
                        f"expected_ids={expected_ids}, returned_ids={returned_ids}, "
                        f"attempt={attempt}/{max_attempts}"
                    )
                raise RuntimeError(f"Incomplete Vision batch: {last_problem}")

            with ThreadPoolExecutor(max_workers=concurrency) as pool:
                scored_batches = list(pool.map(score_batch, batches))
            all_s = [score for batch in scored_batches for score in batch]
            logger.info(
                "doubao_vision_batches_completed",
                extra={
                    "task_id": tid,
                    "video_id": vid,
                    "batch_count": len(batches),
                    "boundary_count": len(all_s),
                },
            )

            rt = int((time.monotonic() - t0) * 1000)
            self._last_result = {"video_id": vid, "scores": all_s}
            return self._ok(tid, vid, sv, "location_character_scores", len(all_s), rt)

        except SeedVisionAPIError as e:
            return self._e(tid, vid, sv, "VISION_INFERENCE_FAILED", str(e), e.retryable)
        except Exception as e:
            return self._e(tid, vid, sv, "VISION_INFERENCE_FAILED", str(e), True)

    def health_check(self) -> bool:
        return self._provider is not None and self._provider.health_check()

    # ------------------------------------------------------------------
    # URI helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _r(u: str) -> str:
        p = "storage://"
        return (
            os.path.join(os.getenv("STORAGE_ROOT", "./data"), u[len(p) :]) if u.startswith(p) else u
        )

    @staticmethod
    def _d(u: str) -> str:
        return DoubaoVisionAdapter._r(u)

    # ------------------------------------------------------------------
    # Envelope
    # ------------------------------------------------------------------

    @staticmethod
    def _ok(t, v, s, k, c, m):
        return {
            "schema_version": s,
            "task_id": t,
            "video_id": v,
            "status": "SUCCEEDED",
            "model": {"name": "doubao_vision", "version": "1.0.0"},
            "artifacts": {k: ""},
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
            "model": {"name": "doubao_vision", "version": "1.0.0"},
            "artifacts": {},
            "metrics": {},
            "error": {"code": c, "message": m, "retryable": r},
        }
