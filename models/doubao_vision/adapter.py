"""Doubao Vision Adapter — shot descriptors, task memory, and boundary evidence."""

from __future__ import annotations

import base64
import copy
import json
import logging
import os
import time
from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor, as_completed
from difflib import SequenceMatcher
from typing import Any

from models.base.adapter import BaseModelAdapter
from models.doubao_vision.providers.seedvision import SeedVisionAPIError, SeedVisionProvider
from models.vlm_boundary.prompts import SHOT_DESCRIPTOR_SYSTEM, SHOT_DESCRIPTOR_TEMPLATE

MAX_ATTEMPTS = 2
MAX_REGISTRY_ITEMS = 24
DEFAULT_CONCURRENCY = 3

logger = logging.getLogger(__name__)


def _encode_image(path: str) -> str:
    with open(path, "rb") as image_file:
        encoded = base64.b64encode(image_file.read()).decode("ascii")
    return "data:image/jpeg;base64," + encoded


def _norm(value: Any) -> str:
    return " ".join(str(value or "").strip().lower().split())


def _set_change(left: Any, right: Any) -> float:
    a = {_norm(item) for item in (left or []) if _norm(item)}
    b = {_norm(item) for item in (right or []) if _norm(item)}
    if not a and not b:
        return 0.0
    return 1.0 - len(a & b) / len(a | b)


def _value_change(left: Any, right: Any) -> float:
    a, b = _norm(left), _norm(right)
    if not a or not b or "unknown" in (a, b):
        return 0.0
    return 0.0 if a == b else 1.0


def _tokens(value: Any) -> set[str]:
    if isinstance(value, list):
        value = " ".join(str(item) for item in value)
    return {token for token in _norm(value).replace("_", " ").split() if len(token) > 1}


def _similarity(left: Any, right: Any) -> float:
    a, b = _norm(left), _norm(right)
    if not a or not b or "unknown" in (a, b):
        return 0.0
    token_a, token_b = _tokens(a), _tokens(b)
    jaccard = len(token_a & token_b) / max(1, len(token_a | token_b))
    return max(jaccard, SequenceMatcher(None, a, b).ratio())


def _match_location(location: dict, locations: dict[str, dict]) -> str:
    best_id, best_score = "", 0.0
    for location_id, known in locations.items():
        features = known.get("features") or known
        environment = _similarity(location.get("environment"), features.get("environment"))
        place_type = _similarity(location.get("place_type"), features.get("place_type"))
        stable = max(
            _similarity(location.get("landmarks"), features.get("landmarks")),
            _similarity(location.get("spatial_layout"), features.get("spatial_layout")),
            _similarity(
                location.get("background_objects"), features.get("background_objects")
            ),
        )
        score = 0.20 * environment + 0.35 * place_type + 0.45 * stable
        if score > best_score:
            best_id, best_score = location_id, score
    return best_id if best_score >= 0.72 else ""


def _match_character(character: dict, characters: dict[str, dict]) -> str:
    description = character.get("stable_description")
    best_id, best_score = "", 0.0
    for character_id, known in characters.items():
        score = _similarity(description, known.get("stable_description"))
        if score > best_score:
            best_id, best_score = character_id, score
    return best_id if best_score >= 0.84 else ""


def _location_change(previous: dict, current: dict) -> tuple[float, dict]:
    a, b = previous["location"], current["location"]
    same_identity = bool(a.get("location_id") and a.get("location_id") == b.get("location_id"))
    evidence = {
        "identity": 0.0 if same_identity else 1.0,
        "environment": _value_change(a.get("environment"), b.get("environment")),
        "place_type": _value_change(a.get("place_type"), b.get("place_type")),
        "spatial_layout": _set_change(a.get("spatial_layout"), b.get("spatial_layout")),
        "landmarks": _set_change(a.get("landmarks"), b.get("landmarks")),
        "background_objects": _set_change(a.get("background_objects"), b.get("background_objects")),
        "architecture": _value_change(a.get("architecture_style"), b.get("architecture_style")),
        "materials": _set_change(a.get("materials"), b.get("materials")),
        "appearance": (
            _set_change(a.get("dominant_colors"), b.get("dominant_colors"))
            + _value_change(a.get("lighting"), b.get("lighting"))
            + _value_change(a.get("time_of_day"), b.get("time_of_day"))
            + _value_change(a.get("weather"), b.get("weather"))
        )
        / 4.0,
    }
    weights = {
        "identity": 0.50,
        "environment": 0.05,
        "place_type": 0.10,
        "spatial_layout": 0.10,
        "landmarks": 0.08,
        "background_objects": 0.05,
        "architecture": 0.05,
        "materials": 0.03,
        "appearance": 0.04,
    }
    raw = sum(evidence[name] * weight for name, weight in weights.items())
    confidence = min(float(a.get("confidence", 0.0)), float(b.get("confidence", 0.0)))
    score = raw * (0.6 + 0.4 * max(0.0, min(1.0, confidence)))
    if same_identity:
        score = min(score, 0.25)
    return round(score * 100.0, 2), {**evidence, "same_location_id": same_identity}


def _character_change(previous: dict, current: dict, shot_index: int) -> tuple[float, dict]:
    previous_ids = {item["character_id"] for item in previous["characters"]}
    current_ids = {item["character_id"] for item in current["characters"]}
    union = previous_ids | current_ids
    if not union:
        return 0.0, {"entered": [], "exited": [], "retained": [], "first_appearances": []}

    retained = previous_ids & current_ids
    entered = current_ids - previous_ids
    exited = previous_ids - current_ids
    set_delta = 1.0 - len(retained) / len(union)
    previous_primary = {
        item["character_id"] for item in previous["characters"] if item.get("is_primary")
    }
    current_primary = {
        item["character_id"] for item in current["characters"] if item.get("is_primary")
    }
    primary_union = previous_primary | current_primary
    primary_delta = (
        1.0 - len(previous_primary & current_primary) / len(primary_union)
        if primary_union
        else set_delta
    )
    first_appearances = {
        item["character_id"]
        for item in current["characters"]
        if item.get("first_shot_index") == shot_index
    }
    score = 0.75 * set_delta + 0.25 * primary_delta
    # A genuine first appearance is important, but joining an existing group is
    # not automatically a complete character replacement.
    if first_appearances:
        novelty = len(first_appearances) / max(1, len(current_ids))
        score = max(score, 0.45 + 0.30 * novelty)
    return round(min(1.0, score) * 100.0, 2), {
        "entered": sorted(entered),
        "exited": sorted(exited),
        "retained": sorted(retained),
        "first_appearances": sorted(first_appearances),
    }


class DoubaoVisionAdapter(BaseModelAdapter):
    """Build shot descriptors and stable task-level location/character identities."""

    name = "doubao_vision"
    version = "1.2.0"

    def __init__(
        self,
        *,
        resume_state: dict[str, Any] | None = None,
        checkpoint_callback: Callable[[dict[str, Any]], None] | None = None,
    ) -> None:
        self._provider: SeedVisionProvider | None = None
        self._loaded = False
        self._last_result: dict[str, Any] = {}
        self._resume_state = resume_state or {}
        self._checkpoint_callback = checkpoint_callback

    def load(self, api_key: str | None = None) -> None:
        if not self._loaded:
            self._provider = SeedVisionProvider(api_key=api_key)
            self._loaded = True

    def unload(self) -> None:
        if self._provider is not None:
            self._provider.close()
        self._provider = None
        self._loaded = False

    def predict(self, model_input: dict[str, Any]) -> dict[str, Any]:
        if not self._loaded:
            self.load()
        provider = self._provider
        if provider is None:
            return self._error("", "", "1.0", "PROVIDER_NOT_LOADED", "Provider not loaded", False)

        schema_version = model_input.get("schema_version", "1.0")
        task_id = model_input["task_id"]
        video_id = model_input["video_id"]
        run_id = str(model_input.get("run_id", ""))
        parameters = model_input.get("parameters", {})
        max_attempts = max(1, min(3, int(parameters.get("max_attempts", MAX_ATTEMPTS))))
        concurrency = max(
            1, min(4, int(parameters.get("concurrency", DEFAULT_CONCURRENCY)))
        )

        try:
            shots = self._load_shots(model_input["input"]["shots_uri"])
            samples = self._load_samples(model_input["input"]["keyframes_uri"])
            if len(shots) < 2:
                return self._error(
                    task_id,
                    video_id,
                    schema_version,
                    "TOO_FEW_SHOTS",
                    "Need at least 2 shots",
                    False,
                )

            location_registry, character_registry, descriptors = self._restore_checkpoint(shots)
            t0 = time.monotonic()
            next_index = len(descriptors)
            while next_index < len(shots):
                batch = list(enumerate(shots[next_index : next_index + concurrency], next_index))
                location_snapshot = copy.deepcopy(location_registry)
                character_snapshot = copy.deepcopy(character_registry)
                completed: dict[int, tuple[dict, int]] = {}
                with ThreadPoolExecutor(max_workers=concurrency) as pool:
                    futures = {}
                    for index, shot in batch:
                        shot_id = str(shot["shot_id"])
                        duration_ms = max(
                            0, int(shot.get("end_ms", 0)) - int(shot.get("start_ms", 0))
                        )
                        frame_paths = self._shot_frames(shot_id, samples, duration_ms)
                        logger.info(
                            "doubao_vision_shot_started",
                            extra={
                                "task_id": task_id,
                                "video_id": video_id,
                                "run_id": run_id,
                                "model": self.name,
                                "shot_id": shot_id,
                                "shot_index": index,
                                "frame_count": len(frame_paths),
                            },
                        )
                        started = time.monotonic()
                        future = pool.submit(
                            self._describe_shot,
                            provider,
                            shot_id,
                            frame_paths,
                            location_snapshot,
                            character_snapshot,
                            max_attempts,
                        )
                        futures[future] = (index, shot_id, started)
                    for future in as_completed(futures):
                        index, shot_id, started = futures[future]
                        elapsed_ms = int((time.monotonic() - started) * 1000)
                        completed[index] = (future.result(), elapsed_ms)

                for index, _shot in batch:
                    raw, elapsed_ms = completed[index]
                    descriptor = self._register_descriptor(
                        raw, index, location_registry, character_registry
                    )
                    descriptors.append(descriptor)
                    logger.info(
                        "doubao_vision_shot_completed",
                        extra={
                            "task_id": task_id,
                            "video_id": video_id,
                            "run_id": run_id,
                            "model": self.name,
                            "shot_id": descriptor["shot_id"],
                            "shot_index": index,
                            "elapsed_ms": elapsed_ms,
                        },
                    )
                if self._checkpoint_callback is not None:
                    self._checkpoint_callback(
                        copy.deepcopy(
                            {
                                "shot_descriptors": descriptors,
                                "location_registry": list(location_registry.values()),
                                "character_registry": list(character_registry.values()),
                            }
                        )
                    )
                next_index += len(batch)

            scores = []
            for index, (previous, current) in enumerate(
                zip(descriptors, descriptors[1:], strict=False)
            ):
                location_score, location_evidence = _location_change(previous, current)
                character_score, character_evidence = _character_change(
                    previous, current, index + 1
                )
                scores.append(
                    {
                        "shot_id": previous["shot_id"],
                        "location_change": location_score,
                        "character_group_change": character_score,
                        "location_evidence": location_evidence,
                        "character_evidence": character_evidence,
                        "previous_location_id": previous["location"]["location_id"],
                        "next_location_id": current["location"]["location_id"],
                    }
                )

            runtime_ms = int((time.monotonic() - t0) * 1000)
            self._last_result = {
                "video_id": video_id,
                "shot_descriptors": descriptors,
                "location_registry": list(location_registry.values()),
                "character_registry": list(character_registry.values()),
                "scores": scores,
            }
            logger.info(
                "doubao_vision_shot_descriptors_completed",
                extra={
                    "task_id": task_id,
                    "video_id": video_id,
                    "run_id": run_id,
                    "model": self.name,
                    "shot_count": len(shots),
                },
            )
            return self._success(task_id, video_id, schema_version, len(scores), runtime_ms)
        except SeedVisionAPIError as exc:
            return self._error(
                task_id,
                video_id,
                schema_version,
                "VISION_INFERENCE_FAILED",
                str(exc),
                exc.retryable,
            )
        except Exception as exc:
            return self._error(
                task_id, video_id, schema_version, "VISION_INFERENCE_FAILED", str(exc), True
            )

    def _describe_shot(
        self,
        provider: SeedVisionProvider,
        shot_id: str,
        frame_paths: list[str],
        locations: dict[str, dict],
        characters: dict[str, dict],
        max_attempts: int,
    ) -> dict:
        location_memory = [
            {
                "location_id": item["location_id"],
                "environment": item["environment"],
                "place_type": item["place_type"],
                "summary": item["summary"],
            }
            for item in list(locations.values())[-MAX_REGISTRY_ITEMS:]
        ]
        character_memory = [
            {
                "character_id": item["character_id"],
                "stable_description": item["stable_description"],
            }
            for item in list(characters.values())[-MAX_REGISTRY_ITEMS:]
        ]
        content: list[dict[str, Any]] = [
            {
                "type": "text",
                "text": SHOT_DESCRIPTOR_TEMPLATE.format(
                    shot_id=shot_id,
                    location_registry=json.dumps(location_memory, ensure_ascii=False),
                    character_registry=json.dumps(character_memory, ensure_ascii=False),
                ),
            }
        ]
        for frame_path in frame_paths:
            content.append({"type": "image_url", "image_url": {"url": _encode_image(frame_path)}})
        messages = [
            {"role": "system", "content": SHOT_DESCRIPTOR_SYSTEM},
            {"role": "user", "content": content},
        ]
        problem = "no response"
        for attempt in range(1, max_attempts + 1):
            try:
                data = provider.send(messages, max_tokens=900).get("data", {})
            except SeedVisionAPIError as exc:
                if not exc.retryable or attempt >= max_attempts:
                    raise
                logger.warning(
                    "doubao_vision_descriptor_retry",
                    extra={"shot_id": shot_id, "attempt": attempt, "error": str(exc)},
                )
                continue
            if (
                isinstance(data, dict)
                and isinstance(data.get("location"), dict)
                and isinstance(data.get("characters"), list)
            ):
                return {**data, "shot_id": shot_id}
            problem = f"invalid descriptor, attempt={attempt}/{max_attempts}"
        raise RuntimeError(f"Incomplete Vision shot descriptor: {problem}")

    def _restore_checkpoint(
        self, shots: list[dict]
    ) -> tuple[dict[str, dict], dict[str, dict], list[dict]]:
        descriptors = list(self._resume_state.get("shot_descriptors") or [])
        expected_prefix = [str(shot["shot_id"]) for shot in shots[: len(descriptors)]]
        actual_prefix = [str(item.get("shot_id", "")) for item in descriptors]
        if actual_prefix != expected_prefix:
            logger.warning("doubao_vision_checkpoint_rejected")
            return {}, {}, []
        locations = {
            str(item["location_id"]): item
            for item in self._resume_state.get("location_registry") or []
            if isinstance(item, dict) and item.get("location_id")
        }
        characters = {
            str(item["character_id"]): item
            for item in self._resume_state.get("character_registry") or []
            if isinstance(item, dict) and item.get("character_id")
        }
        if descriptors:
            logger.info(
                "doubao_vision_checkpoint_restored",
                extra={"completed_shots": len(descriptors)},
            )
        return locations, characters, descriptors

    @staticmethod
    def _register_descriptor(
        raw: dict,
        shot_index: int,
        locations: dict[str, dict],
        characters: dict[str, dict],
    ) -> dict:
        location = raw["location"]
        matched_location = str(location.get("matched_location_id") or "")
        if matched_location not in locations:
            matched_location = _match_location(location, locations)
        if matched_location not in locations:
            matched_location = f"location_{len(locations) + 1:04d}"
            locations[matched_location] = {
                "location_id": matched_location,
                "environment": _norm(location.get("environment")) or "unknown",
                "place_type": _norm(location.get("place_type")) or "unknown",
                "summary": "; ".join(
                    str(item)
                    for item in (location.get("landmarks") or location.get("spatial_layout") or [])
                )[:500],
                "features": {
                    key: location.get(key)
                    for key in (
                        "environment",
                        "place_type",
                        "spatial_layout",
                        "landmarks",
                        "background_objects",
                        "materials",
                    )
                },
                "first_shot_index": shot_index,
            }
        canonical_location = {**location, "location_id": matched_location}
        canonical_location["confidence"] = max(
            0.0, min(1.0, float(canonical_location.get("confidence", 0.0)))
        )

        canonical_characters = []
        for item in raw.get("characters", []):
            if not isinstance(item, dict):
                continue
            matched_character = str(item.get("matched_character_id") or "")
            if matched_character not in characters:
                matched_character = _match_character(item, characters)
            if matched_character not in characters:
                matched_character = f"character_{len(characters) + 1:04d}"
                characters[matched_character] = {
                    "character_id": matched_character,
                    "stable_description": str(item.get("stable_description", "unknown"))[:500],
                    "first_shot_index": shot_index,
                }
            canonical_characters.append(
                {
                    **item,
                    "character_id": matched_character,
                    "first_shot_index": characters[matched_character]["first_shot_index"],
                    "visibility": max(0.0, min(1.0, float(item.get("visibility", 0.0)))),
                    "is_primary": bool(item.get("is_primary", False)),
                }
            )
        return {
            "shot_id": str(raw["shot_id"]),
            "location": canonical_location,
            "characters": canonical_characters,
            "quality": raw.get("quality", {}),
            "reason": raw.get("reason", ""),
        }

    def _load_shots(self, uri: str) -> list[dict]:
        with open(self._resolve(uri), encoding="utf-8") as file:
            return json.load(file).get("shots", [])

    def _load_samples(self, uri: str) -> dict[str, dict[tuple[int, int], str]]:
        with open(self._resolve(uri), encoding="utf-8") as file:
            summary = json.load(file)
        return {
            str(item["shot_id"]): {
                (int(sample["position_num"]), int(sample["position_den"])): str(sample["uri"])
                for sample in item.get("samples", [])
                if sample.get("uri")
            }
            for item in summary.get("shots", [])
        }

    def _shot_frames(self, shot_id: str, samples: dict, duration_ms: int = 0) -> list[str]:
        if 0 < duration_ms < 1000:
            positions = ((1, 2),)
        elif 0 < duration_ms <= 5000:
            positions = ((1, 4), (3, 4))
        else:
            positions = ((1, 4), (1, 2), (3, 4))
        uris = samples.get(shot_id, {})
        paths = [self._resolve(uris.get(position, "")) for position in positions]
        if any(not path or not os.path.isfile(path) for path in paths):
            raise FileNotFoundError(f"Shot {shot_id} is missing required dynamic keyframes")
        return paths

    @staticmethod
    def _resolve(uri: str) -> str:
        prefix = "storage://"
        if uri.startswith(prefix):
            return os.path.join(os.getenv("STORAGE_ROOT", "./data"), uri[len(prefix) :])
        return uri

    def health_check(self) -> bool:
        return self._provider is not None and self._provider.health_check()

    @staticmethod
    def _success(
        task_id: str, video_id: str, schema_version: str, count: int, runtime: int
    ) -> dict:
        return {
            "schema_version": schema_version,
            "task_id": task_id,
            "video_id": video_id,
            "status": "SUCCEEDED",
            "model": {"name": "doubao_vision", "version": "1.2.0"},
            "artifacts": {"location_character_scores": ""},
            "metrics": {"score_count": count, "runtime_ms": runtime},
            "error": None,
        }

    @staticmethod
    def _error(
        task_id: str,
        video_id: str,
        schema_version: str,
        code: str,
        message: str,
        retryable: bool,
    ) -> dict:
        return {
            "schema_version": schema_version,
            "task_id": task_id,
            "video_id": video_id,
            "status": "FAILED",
            "model": {"name": "doubao_vision", "version": "1.2.0"},
            "artifacts": {},
            "metrics": {},
            "error": {"code": code, "message": message, "retryable": retryable},
        }
