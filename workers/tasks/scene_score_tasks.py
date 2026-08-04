"""
Celery tasks for scene scoring — VLM, LLM plot, and score merging.

scene.score_vlm    — Qwen VL location + character scoring
scene.score_plot   — DeepSeek plot event scoring
scene.merge_scores — weighted merge → final scenes
"""

import json
import os
import time
import uuid
from datetime import datetime, timezone

from core.artifacts import ArtifactProducer
from core.artifacts.writer import ArtifactWriter
from core.database.models import ModelRun
from core.database.repositories import (
    ArtifactRepository,
    TaskRepository,
    VideoRepository,
)
from core.database.session_sync import get_sync_session
from core.logging.context import clear_task_context, set_task_context
from core.media.exceptions import NonRetryableTaskError
from workers.celery_app import app


def _resolve_uri(uri: str, storage_root: str) -> str:
    prefix = "storage://"
    if uri.startswith(prefix):
        return os.path.join(storage_root, uri[len(prefix):])
    return uri


# ---------------------------------------------------------------------------
# VLM — Qwen VL location + character scoring
# ---------------------------------------------------------------------------


@app.task(name="scene.score_vlm", bind=True, max_retries=1)
def score_vlm(self, task_id: str, video_id: str) -> dict:
    """Score shot boundaries for location and character change via Qwen VL.

    Reads shots.json + keyframe images, sends to Qwen VL API,
    returns per-boundary location_change + character_group_change scores.
    """
    model_name = "vlm_scene_boundary"
    set_task_context(task_id=task_id, video_id=video_id, model=model_name)
    storage_root = os.getenv("STORAGE_ROOT", "./data")

    with get_sync_session() as session:
        task_repo = TaskRepository(session)
        video_repo = VideoRepository(session)
        artifact_repo = ArtifactRepository(session)

        video = video_repo.get(video_id)
        if video is None:
            clear_task_context()
            raise NonRetryableTaskError(f"[VIDEO_NOT_FOUND] {video_id}")

        # Find shots artifact from same task
        shots_art = artifact_repo.get_artifact_for_task(
            task_id=task_id, video_id=video_id,
            artifact_type="shots", model_name="omnishotcut",
        )
        if shots_art is None:
            clear_task_context()
            raise NonRetryableTaskError("[SHOTS_NOT_FOUND] Run shot.detect first")

        task_repo.update_status(task_id, "RUNNING")
        task_repo.update_progress(task_id, 55, stage="score_vlm")

        run_id = uuid.uuid4().hex[:16]
        model_run = ModelRun(
            run_id=run_id, task_id=task_id, video_id=video_id,
            model_name=model_name, model_version="0.1.0",
            schema_version="1.0", status="RUNNING", device="cpu",
            started_at=datetime.now(timezone.utc),
        )
        session.add(model_run)
        session.commit()

    # Load adapter
    try:
        from models.vlm_boundary.adapter import VLMSceneBoundaryAdapter
    except ImportError as e:
        clear_task_context()
        raise NonRetryableTaskError(f"[IMPORT_FAILED] {e}")

    adapter = VLMSceneBoundaryAdapter()
    try:
        adapter.load()
    except Exception as e:
        with get_sync_session() as session:
            TaskRepository(session).set_error(task_id, "MODEL_LOAD_FAILED", str(e))
            session.commit()
        clear_task_context()
        raise NonRetryableTaskError(f"[MODEL_LOAD_FAILED] {e}")

    # Build keyframe dir path from shots artifact path
    shots_path = _resolve_uri(shots_art.uri, storage_root)
    kf_dir = os.path.join(os.path.dirname(os.path.dirname(shots_path)),
                          "shot_keyframes", "1.0.0")

    try:
        t0 = time.monotonic()
        result = adapter.predict({
            "task_id": task_id, "video_id": video_id,
            "model": {"name": model_name, "version": "0.1.0"},
            "input": {"shots_uri": shots_art.uri, "keyframes_dir": kf_dir},
            "parameters": {"batch_size": 3},
        })
        runtime_ms = int((time.monotonic() - t0) * 1000)
    except Exception as e:
        with get_sync_session() as session:
            TaskRepository(session).set_error(task_id, "VLM_INFERENCE_FAILED", str(e))
            mr = session.get(ModelRun, run_id)
            if mr: mr.status = "FAILED"; mr.finished_at = datetime.now(timezone.utc)
            session.commit()
        clear_task_context()
        raise NonRetryableTaskError(f"[VLM_INFERENCE_FAILED] {e}")

    if result.get("status") != "SUCCEEDED":
        err = result.get("error", {})
        with get_sync_session() as session:
            TaskRepository(session).set_error(task_id, err.get("code", "FAILED"), err.get("message", ""))
            session.commit()
        clear_task_context()
        raise NonRetryableTaskError(f"[{err.get('code', 'FAILED')}] {err.get('message', '')}")

    # Save scores
    scores = adapter._last_result.get("scores", [])
    project_id = video.project_id if video else "default"
    artifact_base = f"projects/{project_id}/videos/{video_id}/artifacts/vlm_boundary/0.1.0"
    scores_rel = f"{artifact_base}/location_character_scores.json"

    writer = ArtifactWriter(storage_root)
    producer = ArtifactProducer(model_name=model_name, model_version="0.1.0")
    manifest = writer.write_json_artifact(
        relative_path=scores_rel,
        data={"video_id": video_id, "scores": scores},
        artifact_type="location_character_scores",
        artifact_id=f"{run_id}_vlm", video_id=video_id, run_id=run_id, producer=producer,
    )

    with get_sync_session() as session:
        ArtifactRepository(session).create(
            artifact_id=f"{run_id}_vlm", video_id=video_id, run_id=run_id,
            artifact_type="location_character_scores",
            uri=f"storage://{scores_rel}", format="json", sha256=manifest.output.sha256,
        )
        mr = session.get(ModelRun, run_id)
        if mr: mr.status = "SUCCEEDED"; mr.runtime_ms = runtime_ms; mr.finished_at = datetime.now(timezone.utc)
        TaskRepository(session).update_progress(task_id, 65, stage="score_vlm")
        session.commit()

    clear_task_context()
    return {
        "task_id": task_id, "video_id": video_id, "run_id": run_id,
        "status": "SUCCEEDED", "stage": "score_vlm",
        "artifacts": {"vlm_scores": f"storage://{scores_rel}"},
        "metrics": {"score_count": len(scores), "runtime_ms": runtime_ms},
    }


# ---------------------------------------------------------------------------
# Plot — DeepSeek event hierarchy + per-boundary scoring
# ---------------------------------------------------------------------------


@app.task(name="scene.score_plot", bind=True, max_retries=1)
def score_plot(self, task_id: str, video_id: str) -> dict:
    """Score shot boundaries for plot change via DeepSeek.

    Reads subtitles.json, sends to DeepSeek for event hierarchy analysis,
    maps events to shot boundaries, returns per-boundary plot_change scores.
    """
    model_name = "deepseek_plot"
    set_task_context(task_id=task_id, video_id=video_id, model=model_name)
    storage_root = os.getenv("STORAGE_ROOT", "./data")

    with get_sync_session() as session:
        task_repo = TaskRepository(session)
        artifact_repo = ArtifactRepository(session)

        # Find subtitles artifact
        sub_art = artifact_repo.get_artifact_for_task(
            task_id=task_id, video_id=video_id,
            artifact_type="subtitle_segments", model_name="whisper",
        )
        if sub_art is None:
            clear_task_context()
            raise NonRetryableTaskError("[SUBTITLES_NOT_FOUND] Run subtitle.transcribe first")

        # Find shots artifact
        shots_art = artifact_repo.get_artifact_for_task(
            task_id=task_id, video_id=video_id,
            artifact_type="shots", model_name="omnishotcut",
        )
        if shots_art is None:
            clear_task_context()
            raise NonRetryableTaskError("[SHOTS_NOT_FOUND] Run shot.detect first")

        task_repo.update_progress(task_id, 70, stage="score_plot")

        run_id = uuid.uuid4().hex[:16]
        model_run = ModelRun(
            run_id=run_id, task_id=task_id, video_id=video_id,
            model_name=model_name, model_version="1.0.0",
            schema_version="1.0", status="RUNNING", device="cpu",
            started_at=datetime.now(timezone.utc),
        )
        session.add(model_run)
        session.commit()

    # Load subtitles + shots
    sub_path = _resolve_uri(sub_art.uri, storage_root)
    shots_path = _resolve_uri(shots_art.uri, storage_root)
    with open(sub_path, encoding="utf-8") as f:
        subtitles = json.load(f).get("subtitle_segments", [])
    with open(shots_path) as f:
        shots = json.load(f).get("shots", [])

    # Build prompt
    sub_lines = [f"[{int(s['start_ms']//60000):02d}:{(s['start_ms']%60000)/1000:05.2f}] {s['text'][:80]}" for s in subtitles]
    sub_timeline = "\n".join(sub_lines)

    prompt = f"""你是电影情节分析助手。以下是电影字幕时间线。

请规划叙事事件（大/中/小三层）：

大事件 (major)：类似剧本的"幕"(Act)。
中事件 (medium)：大事件内的阶段。
小事件 (minor)：中事件内的节拍。

每个事件输出 label, level, time_range(起止ms)。

只输出JSON：
{{"events":[{{"label":"...","level":"major","time_range":{{"start_ms":0,"end_ms":600000}}}}]}}

--- 字幕时间线（{len(subtitles)}句，约{subtitles[-1]['end_ms']//60000}分钟）---
{sub_timeline}"""

    try:
        from models.vlm_boundary.providers.deepseek_llm import DeepSeekLLMProvider

        api_key = os.getenv("QWEN_VL_API_KEY", "")
        if not api_key:
            from core.config import get_settings
            api_key = get_settings().qwen_vl_api_key
        provider = DeepSeekLLMProvider(api_key=api_key)

        t0 = time.monotonic()
        result = provider.send([{"role": "user", "content": prompt}], max_tokens=4096, timeout=600)
        runtime_ms = int((time.monotonic() - t0) * 1000)
    except Exception as e:
        with get_sync_session() as session:
            TaskRepository(session).set_error(task_id, "PLOT_INFERENCE_FAILED", str(e))
            session.commit()
        clear_task_context()
        raise NonRetryableTaskError(f"[PLOT_INFERENCE_FAILED] {e}")

    # Parse events + map to shot boundaries
    raw = result.get("data", {})
    raw_text = raw.get("raw", str(raw))
    events = raw.get("events", [])
    if not events:
        try:
            events = json.loads(raw_text).get("events", [])
        except json.JSONDecodeError:
            import re
            m = re.search(r'\{[\s\S]*"events"[\s\S]*\}', raw_text)
            events = json.loads(m.group()).get("events", []) if m else []

    LEVEL_SCORE = {"major": 100, "medium": 60, "minor": 30}
    plot_scores = []
    for i, shot in enumerate(shots[:-1]):
        boundary_ms = shot["end_ms"]
        max_score = 0
        for evt in events:
            tr = evt.get("time_range", {})
            evt_start = tr.get("start_ms", 0)
            evt_end = tr.get("end_ms", 0)
            if evt_start <= boundary_ms < evt_end:
                continue
            if abs(boundary_ms - evt_start) < 500:
                score = LEVEL_SCORE.get(evt.get("level", "minor"), 30)
                if score > max_score: max_score = score
        if max_score > 0:
            plot_scores.append({"shot_id": shot["shot_id"], "plot_change": max_score})

    # Save
    project_id = "default"
    with get_sync_session() as session:
        video = VideoRepository(session).get(video_id)
        if video: project_id = video.project_id or "default"

    artifact_base = f"projects/{project_id}/videos/{video_id}/artifacts/deepseek_plot/1.0.0"
    scores_rel = f"{artifact_base}/plot_scores.json"
    writer = ArtifactWriter(storage_root)
    producer = ArtifactProducer(model_name=model_name, model_version="1.0.0")
    manifest = writer.write_json_artifact(
        relative_path=scores_rel,
        data={"video_id": video_id, "events": events, "plot_scores": plot_scores},
        artifact_type="plot_scores",
        artifact_id=f"{run_id}_plot", video_id=video_id, run_id=run_id, producer=producer,
    )

    with get_sync_session() as session:
        ArtifactRepository(session).create(
            artifact_id=f"{run_id}_plot", video_id=video_id, run_id=run_id,
            artifact_type="plot_scores", uri=f"storage://{scores_rel}",
            format="json", sha256=manifest.output.sha256,
        )
        mr = session.get(ModelRun, run_id)
        if mr: mr.status = "SUCCEEDED"; mr.runtime_ms = runtime_ms; mr.finished_at = datetime.now(timezone.utc)
        TaskRepository(session).update_progress(task_id, 80, stage="score_plot")
        session.commit()

    clear_task_context()
    return {
        "task_id": task_id, "video_id": video_id, "run_id": run_id,
        "status": "SUCCEEDED", "stage": "score_plot",
        "artifacts": {"plot_scores": f"storage://{scores_rel}"},
        "metrics": {"event_count": len(events), "plot_score_count": len(plot_scores),
                    "runtime_ms": runtime_ms},
    }


# ---------------------------------------------------------------------------
# Merge — weighted scores → final scenes
# ---------------------------------------------------------------------------


@app.task(name="scene.merge_scores", bind=True, max_retries=1)
def merge_scores(self, task_id: str, video_id: str) -> dict:
    """Merge VLM + Plot scores into scene_score, greedily select final scenes.

    Reads location_character_scores + plot_scores + shots.json.
    Weighted merge: 0.35*location + 0.35*character + 0.30*plot.
    Saves final_result.json.
    """
    model_name = "scene_merger"
    set_task_context(task_id=task_id, video_id=video_id, model=model_name)
    storage_root = os.getenv("STORAGE_ROOT", "./data")

    with get_sync_session() as session:
        task_repo = TaskRepository(session)
        artifact_repo = ArtifactRepository(session)

        # Resolve artifacts
        shots_art = artifact_repo.get_artifact_for_task(task_id, video_id, "shots", "omnishotcut")
        vlm_art = artifact_repo.get_artifact_for_task(task_id, video_id, "location_character_scores", "vlm_scene_boundary")
        plot_art = artifact_repo.get_artifact_for_task(task_id, video_id, "plot_scores", "deepseek_plot")

        if not shots_art:
            clear_task_context(); raise NonRetryableTaskError("[SHOTS_NOT_FOUND]")

        task_repo.update_progress(task_id, 85, stage="merge_scores")
        run_id = uuid.uuid4().hex[:16]
        model_run = ModelRun(
            run_id=run_id, task_id=task_id, video_id=video_id,
            model_name=model_name, model_version="1.0.0",
            schema_version="1.0", status="RUNNING", device="cpu",
            started_at=datetime.now(timezone.utc),
        )
        session.add(model_run)
        session.commit()

    # Load all data
    shots_path = _resolve_uri(shots_art.uri, storage_root)
    with open(shots_path) as f:
        shots = json.load(f)["shots"]
    n = len(shots)

    vlm_scores = {}
    if vlm_art:
        with open(_resolve_uri(vlm_art.uri, storage_root), encoding="utf-8") as f:
            vlm_scores = {s["shot_id"]: s for s in json.load(f).get("scores", [])}

    plot_by_shot = {}
    if plot_art:
        with open(_resolve_uri(plot_art.uri, storage_root), encoding="utf-8") as f:
            for p in json.load(f).get("plot_scores", []):
                plot_by_shot[p["shot_id"]] = p

    # Merge
    W = (0.35, 0.35, 0.30)
    THRESHOLD, MIN_SCENE_MS = 50, 30000
    merged, final_scenes = [], []
    scene_start, scene_start_shot = shots[0]["start_ms"], shots[0]["shot_id"]

    for i, shot in enumerate(shots[:-1]):
        sid = shot["shot_id"]
        q = vlm_scores.get(sid, {})
        loc = q.get("location_change", 0)
        char = q.get("character_group_change", 0)
        p = plot_by_shot.get(sid, {})
        plot = p.get("plot_change", p.get("plot_change_score", 0))
        scene_score = round(W[0] * loc + W[1] * char + W[2] * plot)

        merged.append({"shot_id": sid, "location_change": loc,
                       "character_group_change": char, "plot_change_score": plot,
                       "scene_score": scene_score})

        dur = shot["end_ms"] - scene_start
        if scene_score >= THRESHOLD and dur >= MIN_SCENE_MS:
            final_scenes.append({"start_shot": scene_start_shot, "end_shot": sid,
                                 "start_ms": scene_start, "end_ms": shot["end_ms"],
                                 "scene_score": scene_score})
            scene_start = shots[i + 1]["start_ms"]
            scene_start_shot = shots[i + 1]["shot_id"]

    final_scenes.append({"start_shot": scene_start_shot, "end_shot": shots[-1]["shot_id"],
                         "start_ms": scene_start, "end_ms": shots[-1]["end_ms"],
                         "scene_score": 0})

    # Save
    project_id = "default"
    with get_sync_session() as session:
        v = VideoRepository(session).get(video_id)
        if v: project_id = v.project_id or "default"

    artifact_base = f"projects/{project_id}/videos/{video_id}/artifacts/{model_name}/1.0.0"
    result_rel = f"{artifact_base}/final_result.json"
    writer = ArtifactWriter(storage_root)
    producer = ArtifactProducer(model_name=model_name, model_version="1.0.0")
    out = {
        "video_id": video_id, "shot_count": n, "boundary_count": n - 1,
        "weights": {"location": W[0], "character": W[1], "plot": W[2]},
        "threshold": THRESHOLD, "min_scene_ms": MIN_SCENE_MS,
        "merged_scores": merged, "final_scenes": final_scenes,
    }
    manifest = writer.write_json_artifact(
        relative_path=result_rel, data=out,
        artifact_type="final_result",
        artifact_id=f"{run_id}_result", video_id=video_id, run_id=run_id, producer=producer,
    )

    with get_sync_session() as session:
        ArtifactRepository(session).create(
            artifact_id=f"{run_id}_result", video_id=video_id, run_id=run_id,
            artifact_type="final_result", uri=f"storage://{result_rel}",
            format="json", sha256=manifest.output.sha256,
        )
        mr = session.get(ModelRun, run_id)
        if mr: mr.status = "SUCCEEDED"; mr.finished_at = datetime.now(timezone.utc)
        TaskRepository(session).update_progress(task_id, 95, stage="merge_scores")
        session.commit()

    clear_task_context()
    return {
        "task_id": task_id, "video_id": video_id, "run_id": run_id,
        "status": "SUCCEEDED", "stage": "merge_scores",
        "artifacts": {"final_result": f"storage://{result_rel}"},
        "metrics": {"scene_count": len(final_scenes)},
    }
