"""Cached, batched hierarchical subtitle-semantic continuity analysis."""

from __future__ import annotations

import json
import logging
import math
import threading
import time
from bisect import bisect_left
from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Any

from models.base.adapter import BaseModelAdapter
from models.subtitle_semantic.prompts import (
    GLOBAL_USER,
    JSON_REPAIR_USER,
    LOCAL_BATCH_USER,
    RESCORE_USER,
    SUMMARY_SYSTEM,
    SUMMARY_USER,
)
from schemas.subtitle import SubtitleBoundaryContinuity, SubtitleContinuityArtifact

logger = logging.getLogger(__name__)
REASON_MAX_CHARS = 160
LOCAL_BATCH_INTERVALS = 3


class SubtitleSemanticAdapter(BaseModelAdapter):
    """Discover narrative transitions with independently cached LLM phases."""

    name = "subtitle_semantic"
    version = "1.1.0"

    def __init__(self, provider=None, stage_cache=None) -> None:
        self._provider = provider
        self._stage_cache = stage_cache
        self._loaded = provider is not None
        self._last_result: dict[str, Any] = {}
        self._request_metrics: list[dict[str, Any]] = []
        self._metrics_lock = threading.Lock()
        self._cache_hits = 0
        self._cache_misses = 0

    def load(self) -> None:
        if self._loaded:
            return
        from core.config import get_settings
        from models.vlm_boundary.providers.deepseek_llm import DeepSeekLLMProvider

        settings = get_settings()
        if not settings.deepseek_api_key:
            raise RuntimeError("DEEPSEEK_API_KEY is required for subtitle semantic analysis")
        self._provider = DeepSeekLLMProvider(
            api_key=settings.deepseek_api_key,
            model=settings.subtitle_llm_model,
            base_url=settings.subtitle_llm_base_url,
        )
        self._loaded = True

    def unload(self) -> None:
        if self._provider is not None and hasattr(self._provider, "session"):
            self._provider.session.close()
        self._provider = None
        self._loaded = False

    def health_check(self) -> bool:
        return self._provider is not None and self._provider.health_check()

    def predict(self, model_input: dict[str, Any]) -> dict[str, Any]:
        task_id = str(model_input.get("task_id", "unknown"))
        video_id = str(model_input.get("video_id", "unknown"))
        try:
            data = model_input.get("input", {})
            subtitles = _normalise_subtitles(data.get("subtitle_segments", []))
            shots = sorted(data.get("shots", []), key=lambda item: int(item["start_ms"]))
            params = model_input.get("parameters", {})
            if len(shots) < 2 or not subtitles:
                self._last_result = SubtitleContinuityArtifact(
                    video_id=video_id,
                    boundaries=[],
                    analysis={"reason": "no_subtitle_evidence"},
                ).model_dump()
                return self._success(task_id, video_id, 0, 0)
            if not self._loaded:
                self.load()

            started = time.monotonic()
            chunks = _chunk_subtitles(
                subtitles,
                max_chars=int(params.get("summary_chunk_chars", 12_000)),
                max_duration_ms=int(params.get("summary_chunk_duration_ms", 900_000)),
            )
            summaries = [self._summarise(chunk) for chunk in chunks]
            duration_ms = max(1, subtitles[-1]["end_ms"] - subtitles[0]["start_ms"])
            configured_global_limit = min(10, max(1, int(params.get("global_limit", 10))))
            effective_global_limit = min(
                configured_global_limit, _dynamic_global_limit(duration_ms)
            )
            major = self._discover_global(summaries, effective_global_limit)
            local, local_stats = self._discover_local(
                subtitles,
                major,
                start_ms=int(subtitles[0]["start_ms"]),
                end_ms=int(subtitles[-1]["end_ms"]) + 1,
                limit=min(5, max(1, int(params.get("local_limit", 5)))),
                concurrency=min(4, max(1, int(params.get("local_concurrency", 3)))),
                min_chars=max(0, int(params.get("local_min_chars", 40))),
                min_segments=max(1, int(params.get("local_min_segments", 3))),
            )
            mapped = _map_candidates_to_shots(
                major + local,
                shots,
                max_snap_ms=int(params.get("max_snap_ms", 8_000)),
                max_snap_shots=int(params.get("max_snap_shots", 2)),
            )
            boundaries = self._rescore(
                mapped,
                subtitles,
                int(params.get("context_ms", 90_000)),
                int(params.get("rescore_batch_size", 20)),
            )
            runtime_ms = int((time.monotonic() - started) * 1000)
            self._last_result = SubtitleContinuityArtifact(
                video_id=video_id,
                boundaries=[SubtitleBoundaryContinuity.model_validate(item) for item in boundaries],
                analysis={
                    "summary_count": len(summaries),
                    "configured_global_limit": configured_global_limit,
                    "effective_global_limit": effective_global_limit,
                    "global_candidate_count": len(major),
                    "local_candidate_count": len(local),
                    "mapped_candidate_count": len(mapped),
                    "summaries": summaries,
                    "global_candidates": major,
                    "local_candidates": local,
                    "local_batching": local_stats,
                    "stage_cache": {"hits": self._cache_hits, "misses": self._cache_misses},
                    "requests": self._request_metrics,
                },
            ).model_dump()
            return self._success(task_id, video_id, len(boundaries), runtime_ms)
        except Exception as exc:
            return {
                "schema_version": "1.0",
                "task_id": task_id,
                "video_id": video_id,
                "status": "FAILED",
                "model": {"name": self.name, "version": self.version},
                "artifacts": {},
                "metrics": {},
                "error": {
                    "code": "SUBTITLE_SEMANTIC_ANALYSIS_FAILED",
                    "message": str(exc),
                    "retryable": True,
                },
            }

    def _cached(self, stage: str, payload: dict, compute: Callable[[], dict]) -> dict:
        if self._stage_cache is not None:
            cached = self._stage_cache.get(stage, payload)
            if cached is not None:
                self._cache_hits += 1
                return cached
        self._cache_misses += 1
        data = compute()
        if self._stage_cache is not None:
            self._stage_cache.put(stage, payload, data)
        return data

    def _summarise(self, chunk: dict) -> dict:
        payload = {"chunk": chunk, "prompt_version": "summary-v2"}

        def compute() -> dict:
            data = self._send(
                SUMMARY_USER.format(transcript=_format_subtitles(chunk["segments"])),
                stage=f"summary:{chunk['start_ms']}-{chunk['end_ms']}",
                schema='{"summary":"...","events":[{"timestamp_ms":0,"event":"..."}]}',
                max_tokens=768,
            )
            return {
                "start_ms": chunk["start_ms"],
                "end_ms": chunk["end_ms"],
                "summary": str(data.get("summary", "")),
                "events": data.get("events", []),
            }

        return self._cached("summary", payload, compute)

    def _discover_global(self, summaries: list[dict], limit: int) -> list[dict]:
        payload = {"summaries": summaries, "limit": limit, "prompt_version": "global-v2"}

        def compute() -> dict:
            data = self._send(
                GLOBAL_USER.format(
                    limit=limit, summaries=json.dumps(summaries, ensure_ascii=False)
                ),
                stage="global",
                schema='{"candidates":[{"timestamp_ms":0,"reason":"..."}]}',
                max_tokens=768,
            )
            return {"candidates": _candidate_items(data.get("candidates", []), "global", limit)}

        return self._cached("global", payload, compute).get("candidates", [])

    def _discover_local(
        self,
        subtitles: list[dict],
        major: list[dict],
        *,
        start_ms: int,
        end_ms: int,
        limit: int,
        concurrency: int,
        min_chars: int,
        min_segments: int,
    ) -> tuple[list[dict], dict]:
        anchors = sorted({item["timestamp_ms"] for item in major})
        intervals = _build_local_intervals(
            subtitles,
            [start_ms, *anchors, end_ms],
            min_chars=min_chars,
            min_segments=min_segments,
        )
        results: dict[str, list[dict]] = {}
        missing: list[dict] = []
        for interval in intervals:
            payload = _local_cache_payload(interval, anchors, limit)
            cached = self._stage_cache.get("local", payload) if self._stage_cache else None
            if cached is None:
                self._cache_misses += 1
                missing.append(interval)
            else:
                self._cache_hits += 1
                results[interval["interval_id"]] = cached.get("candidates", [])

        groups = [
            missing[index : index + LOCAL_BATCH_INTERVALS]
            for index in range(0, len(missing), LOCAL_BATCH_INTERVALS)
        ]
        effective_concurrency = concurrency
        batch_requests = 0
        failed_interval_retries = 0
        offset = 0
        while offset < len(groups):
            wave = groups[offset : offset + effective_concurrency]
            rate_limits_before = self._rate_limit_count()
            with ThreadPoolExecutor(max_workers=effective_concurrency) as pool:
                futures = {
                    pool.submit(self._request_local_batch, group, anchors, limit): group
                    for group in wave
                }
                for future in as_completed(futures):
                    group = futures[future]
                    batch_requests += 1
                    try:
                        returned = future.result()
                    except Exception:
                        returned = {}
                    for interval in group:
                        interval_id = interval["interval_id"]
                        candidates = returned.get(interval_id)
                        if candidates is None:
                            failed_interval_retries += 1
                            candidates = self._request_local_batch([interval], anchors, limit).get(
                                interval_id
                            )
                        if candidates is None:
                            raise ValueError(f"Missing local result for interval {interval_id}")
                        results[interval_id] = candidates
                        if self._stage_cache is not None:
                            self._stage_cache.put(
                                "local",
                                _local_cache_payload(interval, anchors, limit),
                                {"candidates": candidates},
                            )
            if self._rate_limit_count() > rate_limits_before:
                effective_concurrency = max(1, effective_concurrency - 1)
            offset += len(wave)

        flattened = [
            candidate
            for interval in intervals
            for candidate in results.get(interval["interval_id"], [])
        ]
        return flattened, {
            "raw_interval_count": max(0, len(anchors) + 1),
            "merged_interval_count": len(intervals),
            "batch_request_count": batch_requests,
            "failed_interval_retries": failed_interval_retries,
            "final_concurrency": effective_concurrency,
        }

    def _request_local_batch(
        self, intervals: list[dict], anchors: list[int], limit: int
    ) -> dict[str, list[dict]]:
        request_intervals = [
            {
                "interval_id": item["interval_id"],
                "start_ms": item["start_ms"],
                "end_ms": item["end_ms"],
                "limit": limit,
                "subtitles": _format_subtitles(item["segments"]),
            }
            for item in intervals
        ]
        expected_ids = {item["interval_id"] for item in intervals}
        data = self._send(
            LOCAL_BATCH_USER.format(
                core_timestamps=anchors,
                intervals=json.dumps(request_intervals, ensure_ascii=False),
            ),
            stage="local_batch:" + ",".join(sorted(expected_ids)),
            schema='{"intervals":[{"interval_id":"i0","candidates":[]}]}',
            max_tokens=max(512, 384 * len(intervals)),
        )
        returned: dict[str, list[dict]] = {}
        for item in data.get("intervals", []):
            interval_id = str(item.get("interval_id", ""))
            interval = next(
                (value for value in intervals if value["interval_id"] == interval_id), None
            )
            if interval is None or interval_id in returned:
                continue
            candidates = _candidate_items(item.get("candidates", []), "local", limit)
            returned[interval_id] = [
                candidate
                for candidate in candidates
                if interval["start_ms"] <= candidate["timestamp_ms"] < interval["end_ms"]
            ]
        return returned

    def _rescore(
        self, mapped: list[dict], subtitles: list[dict], context_ms: int, batch_size: int
    ) -> list[dict]:
        if not mapped:
            return []
        contexts = []
        for index, item in enumerate(mapped):
            timestamp_ms = item["timestamp_ms"]
            nearby = [
                segment
                for segment in subtitles
                if segment["end_ms"] > timestamp_ms - context_ms
                and segment["start_ms"] < timestamp_ms + context_ms
            ]
            contexts.append(
                {
                    "boundary_id": f"b{index}",
                    "timestamp_ms": timestamp_ms,
                    "discovery_sources": item["discovery_sources"],
                    "subtitles": _format_subtitles(nearby),
                }
            )
        returned: dict[str, dict] = {}
        batch_size = min(50, max(1, batch_size))
        for start in range(0, len(contexts), batch_size):
            batch = contexts[start : start + batch_size]
            payload = {"contexts": batch, "prompt_version": "rescore-v2"}

            def compute() -> dict:
                data = self._send(
                    RESCORE_USER.format(contexts=json.dumps(batch, ensure_ascii=False)),
                    stage=f"rescore:{start}-{start + len(batch)}",
                    schema='{"boundaries":[{"boundary_id":"b0","subtitle_continuity":0.0,"reason":"..."}]}',
                    max_tokens=max(768, 96 * len(batch)),
                )
                by_id = {str(item.get("boundary_id")): item for item in data.get("boundaries", [])}
                missing = [item for item in batch if item["boundary_id"] not in by_id]
                if missing:
                    repair = self._send(
                        RESCORE_USER.format(contexts=json.dumps(missing, ensure_ascii=False)),
                        stage=f"rescore_missing:{start}",
                        schema='{"boundaries":[{"boundary_id":"b0","subtitle_continuity":0.0,"reason":"..."}]}',
                        max_tokens=max(512, 96 * len(missing)),
                    )
                    by_id.update(
                        {
                            str(item.get("boundary_id")): item
                            for item in repair.get("boundaries", [])
                        }
                    )
                return {"boundaries": list(by_id.values())}

            cached = self._cached("rescore", payload, compute)
            returned.update(
                {str(item.get("boundary_id")): item for item in cached.get("boundaries", [])}
            )

        result = []
        for index, item in enumerate(mapped):
            response = returned.get(f"b{index}")
            if response is None:
                raise ValueError(f"Missing uniform rescore result for boundary b{index}")
            continuity = min(1.0, max(0.0, float(response["subtitle_continuity"])))
            result.append(
                {
                    "shot_id": item["shot_id"],
                    "boundary_index": item["boundary_index"],
                    "timestamp_ms": item["timestamp_ms"],
                    "subtitle_continuity": round(continuity, 4),
                    "discovery_sources": item["discovery_sources"],
                    "discovery_reasons": item["discovery_reasons"],
                    "reason": _short_reason(response.get("reason", "")),
                }
            )
        return result

    def _send(self, user_content: str, *, stage: str, schema: str, **kwargs) -> dict:
        response = self._provider_send(user_content, stage=stage, **kwargs)
        data = response.get("data", {})
        if isinstance(data, dict) and "raw_text" not in data:
            return data
        raw = str(response.get("raw") or data.get("raw_text", ""))[:12_000]
        repair = self._provider_send(
            JSON_REPAIR_USER.format(schema=schema, raw=raw),
            stage=f"{stage}:json_repair",
            max_tokens=kwargs.get("max_tokens", 768),
            temperature=0,
        )
        repaired_data = repair.get("data", {})
        if not isinstance(repaired_data, dict) or "raw_text" in repaired_data:
            raise ValueError(f"LLM did not return valid JSON for stage {stage}")
        return repaired_data

    def _provider_send(self, user_content: str, *, stage: str, **kwargs) -> dict:
        started = time.monotonic()
        logger.info("subtitle_semantic_request_started", extra={"stage": stage})
        try:
            response = self._provider.send(
                [
                    {"role": "system", "content": SUMMARY_SYSTEM},
                    {"role": "user", "content": user_content},
                ],
                **kwargs,
            )
        except Exception as exc:
            telemetry = {**getattr(exc, "telemetry", {}), "stage": stage, "failed": True}
            telemetry.setdefault("elapsed_ms", int((time.monotonic() - started) * 1000))
            with self._metrics_lock:
                self._request_metrics.append(telemetry)
            logger.warning("subtitle_semantic_request_failed", extra=telemetry)
            raise
        elapsed_ms = int((time.monotonic() - started) * 1000)
        telemetry = {**response.get("telemetry", {}), "stage": stage}
        telemetry.setdefault("elapsed_ms", elapsed_ms)
        with self._metrics_lock:
            self._request_metrics.append(telemetry)
        logger.info(
            "subtitle_semantic_request_finished",
            extra={"stage": stage, **telemetry},
        )
        return response

    def _rate_limit_count(self) -> int:
        with self._metrics_lock:
            return sum(1 for item in self._request_metrics if item.get("rate_limited"))

    def _success(self, task_id: str, video_id: str, count: int, runtime_ms: int) -> dict:
        return {
            "schema_version": "1.0",
            "task_id": task_id,
            "video_id": video_id,
            "status": "SUCCEEDED",
            "model": {"name": self.name, "version": self.version},
            "artifacts": {"subtitle_continuity": ""},
            "metrics": {"boundary_count": count, "runtime_ms": runtime_ms},
            "error": None,
        }


def _dynamic_global_limit(duration_ms: int) -> int:
    """Declining transition density: 3 min→4, 10 min→5, 1 h→10 (capped)."""
    minutes = max(0.1, duration_ms / 60_000)
    return min(10, max(3, round(2 + math.sqrt(minutes))))


def _normalise_subtitles(items: list[dict]) -> list[dict]:
    result = []
    for item in items:
        text = str(item.get("text", "")).strip()
        start_ms = int(item.get("start_ms", 0))
        end_ms = max(start_ms, int(item.get("end_ms", start_ms)))
        if text:
            result.append({"start_ms": start_ms, "end_ms": end_ms, "text": text})
    return sorted(result, key=lambda item: (item["start_ms"], item["end_ms"]))


def _chunk_subtitles(items: list[dict], *, max_chars: int, max_duration_ms: int) -> list[dict]:
    chunks: list[dict] = []
    current: list[dict] = []
    chars = 0
    for item in items:
        duration = item["end_ms"] - current[0]["start_ms"] if current else 0
        if current and (chars + len(item["text"]) > max_chars or duration > max_duration_ms):
            chunks.append(
                {
                    "start_ms": current[0]["start_ms"],
                    "end_ms": current[-1]["end_ms"],
                    "segments": current,
                }
            )
            current = []
            chars = 0
        current.append(item)
        chars += len(item["text"])
    if current:
        chunks.append(
            {
                "start_ms": current[0]["start_ms"],
                "end_ms": current[-1]["end_ms"],
                "segments": current,
            }
        )
    return chunks


def _build_local_intervals(
    subtitles: list[dict], edges: list[int], *, min_chars: int, min_segments: int
) -> list[dict]:
    raw = []
    for start_ms, end_ms in zip(edges, edges[1:], strict=False):
        segments = [
            item for item in subtitles if item["end_ms"] > start_ms and item["start_ms"] < end_ms
        ]
        raw.append({"start_ms": start_ms, "end_ms": end_ms, "segments": segments})
    merged: list[dict] = []
    index = 0
    while index < len(raw):
        item = raw[index]
        chars = sum(len(segment["text"]) for segment in item["segments"])
        tiny = len(item["segments"]) < min_segments or chars < min_chars
        if tiny and index + 1 < len(raw):
            following = raw[index + 1]
            raw[index + 1] = {
                "start_ms": item["start_ms"],
                "end_ms": following["end_ms"],
                "segments": item["segments"] + following["segments"],
            }
        elif tiny and merged:
            merged[-1]["end_ms"] = item["end_ms"]
            merged[-1]["segments"].extend(item["segments"])
        elif item["segments"]:
            merged.append(item)
        index += 1
    for interval_index, item in enumerate(merged):
        item["interval_id"] = f"i{interval_index}"
    return merged


def _local_cache_payload(interval: dict, anchors: list[int], limit: int) -> dict:
    return {
        "start_ms": interval["start_ms"],
        "end_ms": interval["end_ms"],
        "segments": interval["segments"],
        "core_timestamps": anchors,
        "limit": limit,
        "prompt_version": "local-batch-v2",
    }


def _format_subtitles(items: list[dict]) -> str:
    return "\n".join(f"[{item['start_ms']},{item['end_ms']}) {item['text']}" for item in items)


def _short_reason(value: Any) -> str:
    return str(value or "").strip()[:REASON_MAX_CHARS]


def _candidate_items(items: list[dict], source: str, limit: int) -> list[dict]:
    result = []
    for item in items[:limit]:
        try:
            timestamp_ms = max(0, int(item["timestamp_ms"]))
        except (KeyError, TypeError, ValueError):
            continue
        result.append(
            {
                "timestamp_ms": timestamp_ms,
                "reason": _short_reason(item.get("reason", "")),
                "source": source,
            }
        )
    return result


def _map_candidates_to_shots(
    candidates: list[dict],
    shots: list[dict],
    *,
    max_snap_ms: int,
    max_snap_shots: int,
) -> list[dict]:
    boundaries = [int(shot["end_ms"]) for shot in shots[:-1]]
    if not boundaries:
        return []
    merged: dict[int, dict] = {}
    for candidate in candidates:
        timestamp_ms = int(candidate["timestamp_ms"])
        insertion = bisect_left(boundaries, timestamp_ms)
        possible = [index for index in (insertion - 1, insertion) if 0 <= index < len(boundaries)]
        boundary_index = min(possible, key=lambda index: abs(boundaries[index] - timestamp_ms))
        delta_ms = abs(boundaries[boundary_index] - timestamp_ms)
        shot_distance = abs(boundary_index - min(insertion, len(boundaries) - 1))
        if delta_ms > max_snap_ms and shot_distance > max_snap_shots:
            continue
        existing = merged.setdefault(
            boundary_index,
            {
                "shot_id": str(shots[boundary_index]["shot_id"]),
                "boundary_index": boundary_index,
                "timestamp_ms": boundaries[boundary_index],
                "discovery_sources": [],
                "discovery_reasons": [],
            },
        )
        if candidate["source"] not in existing["discovery_sources"]:
            existing["discovery_sources"].append(candidate["source"])
        reason = _short_reason(candidate.get("reason", ""))
        if reason and reason not in existing["discovery_reasons"]:
            existing["discovery_reasons"].append(reason)
    return [merged[index] for index in sorted(merged)]
