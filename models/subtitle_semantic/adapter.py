"""Hierarchical subtitle semantic Adapter producing allowed continuity evidence only."""

from __future__ import annotations

import json
import logging
import time
from bisect import bisect_left
from concurrent.futures import ThreadPoolExecutor
from typing import Any

from models.base.adapter import BaseModelAdapter
from models.subtitle_semantic.prompts import (
    GLOBAL_USER,
    LOCAL_USER,
    RESCORE_USER,
    SUMMARY_SYSTEM,
    SUMMARY_USER,
)
from schemas.subtitle import SubtitleBoundaryContinuity, SubtitleContinuityArtifact

logger = logging.getLogger(__name__)


class SubtitleSemanticAdapter(BaseModelAdapter):
    """Discover narrative transitions hierarchically, then score them uniformly."""

    name = "subtitle_semantic"
    version = "1.0.0"

    def __init__(self, provider=None) -> None:
        self._provider = provider
        self._loaded = provider is not None
        self._last_result: dict[str, Any] = {}

    def load(self) -> None:
        if self._loaded:
            return
        from core.config import get_settings
        from models.vlm_boundary.providers.deepseek_llm import DeepSeekLLMProvider

        settings = get_settings()
        api_key = settings.deepseek_api_key
        if not api_key:
            raise RuntimeError("DEEPSEEK_API_KEY is required for subtitle semantic analysis")
        self._provider = DeepSeekLLMProvider(
            api_key=api_key,
            model=settings.subtitle_llm_model,
            base_url=settings.subtitle_llm_base_url,
        )
        self._loaded = True

    def unload(self) -> None:
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
            major = self._discover_global(
                summaries, limit=min(10, max(1, int(params.get("global_limit", 10))))
            )
            local = self._discover_local(
                summaries,
                major,
                start_ms=int(subtitles[0]["start_ms"]),
                end_ms=int(subtitles[-1]["end_ms"]) + 1,
                limit=min(5, max(1, int(params.get("local_limit", 5)))),
                concurrency=min(4, max(1, int(params.get("local_concurrency", 3)))),
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
                    "global_candidate_count": len(major),
                    "local_candidate_count": len(local),
                    "mapped_candidate_count": len(mapped),
                    "summaries": summaries,
                    "global_candidates": major,
                    "local_candidates": local,
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

    def _summarise(self, chunk: dict) -> dict:
        transcript = _format_subtitles(chunk["segments"])
        data = self._send(
            SUMMARY_USER.format(transcript=transcript),
            stage="summary",
            max_tokens=1024,
        )
        return {
            "start_ms": chunk["start_ms"],
            "end_ms": chunk["end_ms"],
            "summary": str(data.get("summary", "")),
            "events": data.get("events", []),
        }

    def _discover_global(self, summaries: list[dict], limit: int) -> list[dict]:
        data = self._send(
            GLOBAL_USER.format(limit=limit, summaries=json.dumps(summaries, ensure_ascii=False)),
            stage="global",
            max_tokens=1024,
        )
        return _candidate_items(data.get("candidates", []), source="global", limit=limit)

    def _discover_local(
        self,
        summaries: list[dict],
        major: list[dict],
        *,
        start_ms: int,
        end_ms: int,
        limit: int,
        concurrency: int,
    ) -> list[dict]:
        anchors = sorted({item["timestamp_ms"] for item in major})
        edges = [start_ms, *anchors, end_ms]
        requests_to_make: list[tuple[int, int, list[dict]]] = []
        for interval_start, interval_end in zip(edges, edges[1:], strict=False):
            relevant = [
                item
                for item in summaries
                if item["end_ms"] > interval_start and item["start_ms"] < interval_end
            ]
            if not relevant:
                continue
            requests_to_make.append((interval_start, interval_end, relevant))

        def analyse_interval(item: tuple[int, int, list[dict]]) -> list[dict]:
            interval_start, interval_end, relevant = item
            data = self._send(
                LOCAL_USER.format(
                    start_ms=interval_start,
                    end_ms=interval_end,
                    limit=limit,
                    core_timestamps=anchors,
                    summaries=json.dumps(relevant, ensure_ascii=False),
                ),
                stage=f"local:{interval_start}-{interval_end}",
                max_tokens=1024,
            )
            candidates = _candidate_items(data.get("candidates", []), source="local", limit=limit)
            return [
                item for item in candidates if interval_start <= item["timestamp_ms"] < interval_end
            ]

        with ThreadPoolExecutor(max_workers=concurrency) as pool:
            interval_results = list(pool.map(analyse_interval, requests_to_make))
        result = [candidate for interval in interval_results for candidate in interval]
        return result

    def _rescore(
        self,
        mapped: list[dict],
        subtitles: list[dict],
        context_ms: int,
        batch_size: int,
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
        returned = {}
        batch_size = min(50, max(1, batch_size))
        for start in range(0, len(contexts), batch_size):
            batch = contexts[start : start + batch_size]
            data = self._send(
                RESCORE_USER.format(contexts=json.dumps(batch, ensure_ascii=False)),
                stage=f"rescore:{start}-{start + len(batch)}",
                max_tokens=2048,
            )
            returned.update(
                {str(item.get("boundary_id")): item for item in data.get("boundaries", [])}
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
                    "reason": str(response.get("reason", "")),
                }
            )
        return result

    def _send(self, user_content: str, *, stage: str, **kwargs) -> dict:
        started = time.monotonic()
        logger.info("subtitle_semantic_request_started", extra={"stage": stage})
        response = self._provider.send(
            [
                {"role": "system", "content": SUMMARY_SYSTEM},
                {"role": "user", "content": user_content},
            ],
            **kwargs,
        )
        logger.info(
            "subtitle_semantic_request_finished",
            extra={"stage": stage, "elapsed_ms": int((time.monotonic() - started) * 1000)},
        )
        data = response.get("data", {})
        if not isinstance(data, dict) or "raw_text" in data:
            raise ValueError("LLM did not return valid JSON")
        return data

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


def _format_subtitles(items: list[dict]) -> str:
    return "\n".join(f"[{item['start_ms']},{item['end_ms']}) {item['text']}" for item in items)


def _candidate_items(items: list[dict], *, source: str, limit: int) -> list[dict]:
    result = []
    for item in items[:limit]:
        try:
            timestamp_ms = max(0, int(item["timestamp_ms"]))
        except (KeyError, TypeError, ValueError):
            continue
        result.append(
            {
                "timestamp_ms": timestamp_ms,
                "reason": str(item.get("reason", "")),
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
        reason = str(candidate.get("reason", ""))
        if reason and reason not in existing["discovery_reasons"]:
            existing["discovery_reasons"].append(reason)
    return [merged[index] for index in sorted(merged)]
