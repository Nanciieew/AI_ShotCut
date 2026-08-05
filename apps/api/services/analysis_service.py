"""Analysis orchestration service — submits Celery chains for video analysis.

Handles:
  - Creating Project/Video/Task records
  - Delegating to core.orchestration for Celery chain construction
  - Validating preconditions

Per CLAUDE.md §2.1, this service MUST NOT directly define task execution order.
It delegates to core.orchestration canvas builders instead.
"""

import uuid

from core.orchestration import build_omnishotcut_canvas


def _new_id() -> str:
    return uuid.uuid4().hex[:16]


async def submit_full_pipeline(
    db,
    video_path: str,
    project_id: str | None = None,
    extract_keyframes: bool = False,
    scene_analysis: bool = False,
    shot_model: str = "ffmpeg_scene",
    score_mode: str = "weighted",
    location_weight: int = 1,
    character_weight: int = 1,
    plot_weight: int = 1,
    cut_intensity: str = "medium",
    min_distance_s: int = 12,
) -> dict:
    """Create DB records and submit the analysis pipeline chain.

    Parameters
    ----------
    db : AsyncSession
        Database session (async).
    video_path : str
        Path to the source video file.
    project_id : Optional[str]
        Project identifier (default: "default").
    extract_keyframes : bool
        When True, include the keyframe extraction step after shot detection.
    scene_analysis : bool
        When True, run full scene scoring (VLM + LLM + merge).
    score_mode : str
        location_only | character_only | plot_only | custom | weighted
    location_weight : int
        Location weight 1-10 (custom mode only).
    character_weight : int
        Character weight 1-10 (custom mode only).
    plot_weight : int
        Plot weight 1-10 (custom mode only).
    cut_intensity : str
        high (6%%) | medium (4%%) | low (1%%) target scene count.
    min_distance_s : int
        Minimum seconds between selected boundaries (default 12).

    Returns
    -------
    dict
        {task_id, video_id, project_id, status, stage, message}
    """
    from core.database.repositories import (
        TaskRepository,
        VideoRepository,
    )
    from core.database.session_sync import get_sync_session

    vid = _new_id()
    task_id = _new_id()
    proj_id = project_id or "default"

    with get_sync_session() as session:
        video_repo = VideoRepository(session)
        task_repo = TaskRepository(session)

        # Ensure project exists
        video_repo.ensure_project(proj_id, name=proj_id)

        # Create video record + original artifact
        source_uri = f"storage://projects/{proj_id}/videos/{vid}/source/{video_path}"
        video_repo.create(
            video_id=vid,
            project_id=proj_id,
            source_uri=source_uri,
        )

        # Create task
        task_repo.create(
            task_id=task_id,
            video_id=vid,
            task_type="omnishotcut_pipeline",
        )
        session.commit()

    # Start pipeline in background thread (no Redis/Celery dependency)
    import threading

    def run_pipeline():
        """Run the full pipeline synchronously in a background thread."""
        import sys, os, json, time, subprocess, base64, uuid, re
        from pathlib import Path
        sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent.parent))

        storage_root = os.getenv("STORAGE_ROOT", "./data")
        steps_msg = "normalize_video → detect_shots → extract_keyframes"
        if scene_analysis:
            steps_msg += " → transcribe → vlm+plot → merge"
        steps_msg += " → complete"

        with get_sync_session() as session:
            task_repo = TaskRepository(session)
            task_repo.update_status(task_id, "RUNNING")
            task_repo.update_progress(task_id, 5, stage="normalize_video")
            session.commit()

        try:
            # Step 1: Normalize
            from core.media.ffprobe import probe_video, run_ffprobe
            from core.media.ffmpeg import build_normalize_command, run_ffmpeg, get_ffmpeg_version
            from core.media.normalization import validate_normalization
            from core.media.schemas import NormalizationConfig

            if source_uri.startswith("storage://"):
                source_uri = source_uri[len("storage://"):]
            video_path_full = os.path.join(storage_root, source_uri)
            artifact_base = f"projects/{proj_id}/videos/{vid}/artifacts"
            norm_dir = os.path.join(storage_root, artifact_base, "video_normalization", "1.0.0")
            os.makedirs(norm_dir, exist_ok=True)
            normalized_path = os.path.join(norm_dir, "normalized.mp4")

            with get_sync_session() as session:
                task_repo = TaskRepository(session)
                task_repo.update_progress(task_id, 10, stage="normalize_video"); session.commit()

            if not os.path.exists(normalized_path):
                probe_before = run_ffprobe(video_path_full)
                cfg = NormalizationConfig()
                cmd = build_normalize_command(input_path=video_path_full, output_path=normalized_path, probe=probe_before, config=cfg)
                run_ffmpeg(cmd, timeout=3600, description="normalize")
                probe_after = run_ffprobe(normalized_path)
                validate_normalization(probe_before=probe_before, probe_after=probe_after, output_path=normalized_path)
            else:
                probe_after = run_ffprobe(normalized_path)

            nrml_uri = f"storage://{artifact_base}/video_normalization/1.0.0/normalized.mp4"
            with get_sync_session() as session:
                task_repo = TaskRepository(session)
                video_repo = VideoRepository(session)
                video_repo.update_metadata(vid, duration_ms=probe_after.duration_ms, fps_num=probe_after.fps_num, fps_den=probe_after.fps_den, width=probe_after.width, height=probe_after.height, normalized_uri=nrml_uri)
                task_repo.update_progress(task_id, 30, stage="detect_shots"); session.commit()

            # Step 2: Shot detection (skip if shots.json exists)
            shot_dir = os.path.join(storage_root, artifact_base, "omnishotcut", "0.1.0")
            shots_json = os.path.join(shot_dir, "shots.json")
            from models.ffmpeg_scene.adapter import FFmpegSceneAdapter
            adapter = FFmpegSceneAdapter()
            if os.path.exists(shots_json):
                with open(shots_json) as f: adapter._last_result = json.load(f)
            else:
                adapter.predict({"task_id": task_id, "video_id": vid, "model": {"name": "ffmpeg_scene", "version": "0.1.0"}, "input": {"video_uri": nrml_uri}, "parameters": {"threshold": 0.1}})
                os.makedirs(shot_dir, exist_ok=True)
                with open(shots_json, "w") as f: json.dump(adapter._last_result, f)
            shots_list = adapter._last_result.get("shots", [])

            with get_sync_session() as session:
                task_repo = TaskRepository(session)
                task_repo.update_progress(task_id, 40, stage="extract_keyframes"); session.commit()

            # Step 3+4: Keyframes ∥ Subtitle (parallel, skip if exists)
            from concurrent.futures import ThreadPoolExecutor, as_completed
            from core.media.keyframes import compute_keyframe_targets, extract_keyframes

            kf_proxy = os.path.join(storage_root, artifact_base, "shot_keyframes_proxy", "1.0.0")
            os.makedirs(kf_proxy, exist_ok=True)
            kf_done = len(os.listdir(kf_proxy)) > 0 if os.path.isdir(kf_proxy) else False

            segs = []
            with ThreadPoolExecutor(max_workers=2) as pool:
                if not kf_done:
                    targets = compute_keyframe_targets(shots_list, probe_after.fps_num, probe_after.fps_den)
                    kf_future = pool.submit(lambda: extract_keyframes(normalized_path, targets, Path(kf_proxy), max_long_side=320, quality=85))

                if scene_analysis:
                    from models.whisper.adapter import WhisperAdapter
                    wa = WhisperAdapter(); wa.load()
                    sub_future = pool.submit(lambda: wa.predict({"task_id": task_id, "video_id": vid, "model": {"name": "whisper", "version": "1.0.0"}, "input": {"video_uri": nrml_uri}, "parameters": {}}))
                    segs = sub_future.result().get("artifacts", {}).get("subtitle_segments", [])
                if not kf_done:
                    kf_future.result()

            if not scene_analysis:
                with get_sync_session() as session:
                    task_repo = TaskRepository(session)
                    task_repo.update_status(task_id, "SUCCEEDED")
                    task_repo.update_progress(task_id, 100, stage="complete"); session.commit()
                return

            with get_sync_session() as session:
                task_repo = TaskRepository(session)
                task_repo.update_progress(task_id, 60, stage="scoring"); session.commit()

            # Step 5+6: VLM ∥ DeepSeek (parallel, skip if scores exist)
            vlm_scores = []
            plot_scores = []
            vlm_scores_path = os.path.join(storage_root, artifact_base, "vlm_boundary", "0.1.0", "location_character_scores.json")
            plot_scores_path = os.path.join(storage_root, artifact_base, "deepseek_plot", "1.0.0", "plot_scores.json")
            vlm_done = os.path.exists(vlm_scores_path)
            plot_done = os.path.exists(plot_scores_path)

            with ThreadPoolExecutor(max_workers=2) as pool:
                vlm_future = None
                if len(shots_list) >= 2:
                    if vlm_done:
                        with open(vlm_scores_path) as f: vlm_scores = json.load(f).get("scores", [])
                    else:
                        from models.vlm_boundary.adapter import VLMSceneBoundaryAdapter
                        def run_vlm():
                            va = VLMSceneBoundaryAdapter(); va.load()
                            va.predict({"task_id": task_id, "video_id": vid, "model": {"name": "vlm_scene_boundary", "version": "0.1.0"}, "input": {"shots_uri": f"storage://{artifact_base}/omnishotcut/0.1.0/shots.json", "keyframes_dir": kf_proxy}, "parameters": {}})
                            return va._last_result.get("scores", [])
                        vlm_future = pool.submit(run_vlm)

                plot_future = None
                if plot_done:
                    with open(plot_scores_path) as f: plot_scores = json.load(f).get("plot_scores", [])
                elif segs:
                    sub_lines = [f"[{int(s['start_ms']//60000):02d}:{(s['start_ms']%60000)/1000:05.2f}] {s['text'][:80]}" for s in segs]
                    from models.vlm_boundary.providers.deepseek_llm import DeepSeekLLMProvider
                    api_key = os.getenv("QWEN_VL_API_KEY", "")
                    if not api_key:
                        try:
                            from core.config import get_settings; api_key = get_settings().qwen_vl_api_key
                        except Exception: pass
                    if api_key:
                        dp = DeepSeekLLMProvider(api_key=api_key)
                        dprompt = f"你是电影情节分析助手。以下是电影字幕时间线。请规划叙事事件（大/中/小三层）。大事件(major)：类似剧本的'幕'。中事件(medium)：大事件内的阶段。小事件(minor)：中事件内的节拍。每个事件输出label,level,time_range(起止ms)。只输出JSON：{{\"events\":[{{\"label\":\"...\",\"level\":\"major\",\"time_range\":{{\"start_ms\":0,\"end_ms\":600000}}}}]}}\n---\n" + "\n".join(sub_lines)
                        plot_future = pool.submit(lambda: dp.send([{"role": "user", "content": dprompt}], max_tokens=4096, timeout=600))

                # Collect VLM results
                if vlm_future:
                    vlm_scores = vlm_future.result()

                # Collect Plot results
                if plot_future:
                    raw_d = plot_future.result().get("data", {})
                    raw_txt = raw_d.get("raw", str(raw_d))
                    events = raw_d.get("events", [])
                    if not events:
                        try: events = json.loads(raw_txt).get("events", [])
                        except: pass
                    LEVEL = {"major": 100, "medium": 60, "minor": 30}
                    for shot in shots_list[:-1]:
                        bms = shot["end_ms"]; mx = 0
                        for evt in events:
                            tr = evt.get("time_range", {}); es = tr.get("start_ms", 0); ee = tr.get("end_ms", 0)
                            if es <= bms < ee: continue
                            if abs(bms - es) < 500:
                                sc = LEVEL.get(evt.get("level", "minor"), 30)
                                if sc > mx: mx = sc
                        if mx > 0: plot_scores.append({"shot_id": shot["shot_id"], "plot_change": mx})

            # Step 7: Merge (skip if final_result.json exists)
            merge_dir = os.path.join(storage_root, artifact_base, "scene_merger", "1.0.0")
            final_json = os.path.join(merge_dir, "final_result.json")
            if os.path.exists(final_json):
                with get_sync_session() as session:
                    task_repo = TaskRepository(session)
                    task_repo.update_status(task_id, "SUCCEEDED")
                    task_repo.update_progress(task_id, 100, stage="complete"); session.commit()
                return

            with get_sync_session() as session:
                task_repo = TaskRepository(session)
                task_repo.update_progress(task_id, 85, stage="merge_scores"); session.commit()

            # Compute weights
            if score_mode == "location_only": W = (1.0, 0.0, 0.0)
            elif score_mode == "character_only": W = (0.0, 1.0, 0.0)
            elif score_mode == "plot_only": W = (0.0, 0.0, 1.0)
            elif score_mode == "custom":
                total = float(location_weight + character_weight + plot_weight)
                W = (location_weight/total, character_weight/total, plot_weight/total) if total > 0 else (1.0, 0.0, 0.0)

            INTENSITY = {"high": 0.06, "medium": 0.04, "low": 0.01}
            target_count = max(3, int(len(shots_list) * INTENSITY.get(cut_intensity, 0.04)))
            MIN_DIST = min_distance_s * 1000

            vlm_map = {s["shot_id"]: s for s in vlm_scores}
            plot_map = {p["shot_id"]: p for p in plot_scores}
            merged = []
            for i, shot in enumerate(shots_list[:-1]):
                sid = shot["shot_id"]
                q = vlm_map.get(sid, {}); pp = plot_map.get(sid, {})
                scene_score = round(W[0]*q.get("location_change",0) + W[1]*q.get("character_group_change",0) + W[2]*pp.get("plot_change",0))
                merged.append({"shot_id": sid, "boundary_index": i, "timestamp_ms": shot["end_ms"], "location_change": q.get("location_change",0), "character_group_change": q.get("character_group_change",0), "plot_change_score": pp.get("plot_change",0), "scene_score": scene_score})

            ranked = sorted(merged, key=lambda b: b["scene_score"], reverse=True)
            selected = []
            for b in ranked:
                if b["scene_score"] == 0: continue
                if any(abs(b["timestamp_ms"] - s["timestamp_ms"]) < MIN_DIST for s in selected): continue
                selected.append(b)
                if len(selected) >= target_count: break
            selected.sort(key=lambda b: b["timestamp_ms"])

            candidate_boundaries = []
            for s in selected:
                m, sec = divmod(s["timestamp_ms"], 60000)
                candidate_boundaries.append({"shot_id": s["shot_id"], "boundary_index": s["boundary_index"], "timestamp_ms": s["timestamp_ms"], "timestamp_readable": f"{int(m):02d}:{sec/1000:05.2f}", "scene_score": s["scene_score"], "location_change": s["location_change"], "character_group_change": s["character_group_change"], "plot_change_score": s["plot_change_score"]})

            final_scenes = []
            scene_start, scene_start_shot = shots_list[0]["start_ms"], shots_list[0]["shot_id"]
            for b in selected:
                final_scenes.append({"start_shot": scene_start_shot, "end_shot": b["shot_id"], "start_ms": scene_start, "end_ms": b["timestamp_ms"], "scene_score": b["scene_score"]})
                ni = b["boundary_index"] + 1
                scene_start = shots_list[ni]["start_ms"] if ni < len(shots_list) else b["timestamp_ms"]
                scene_start_shot = shots_list[ni]["shot_id"] if ni < len(shots_list) else b["shot_id"]
            final_scenes.append({"start_shot": scene_start_shot, "end_shot": shots_list[-1]["shot_id"], "start_ms": scene_start, "end_ms": shots_list[-1]["end_ms"], "scene_score": 0})

            # Save results
            os.makedirs(merge_dir, exist_ok=True)
            with open(os.path.join(merge_dir, "final_result.json"), "w") as f:
                json.dump({"final_scenes": final_scenes, "candidate_boundaries": candidate_boundaries}, f)

            with get_sync_session() as session:
                task_repo = TaskRepository(session)
                task_repo.update_status(task_id, "SUCCEEDED")
                task_repo.update_progress(task_id, 100, stage="complete"); session.commit()

        except Exception as e:
            import traceback
            traceback.print_exc()
            with get_sync_session() as session:
                task_repo = TaskRepository(session)
                task_repo.set_error(task_id, "PIPELINE_FAILED", str(e)[:500]); session.commit()

    threading.Thread(target=run_pipeline, daemon=True).start()

    return {
        "task_id": task_id,
        "video_id": vid,
        "project_id": proj_id,
        "status": "RUNNING",
        "stage": "normalize_video",
        "progress": 5,
        "message": f"Pipeline started: {steps_msg if scene_analysis else 'normalize → detect → keyframes → complete'}",
    }


async def get_task_status(task_id: str, db) -> dict:
    """Query task status from the database."""
    from sqlalchemy import select

    from core.database.models import Task

    result = await db.execute(select(Task).where(Task.task_id == task_id))
    task = result.scalar_one_or_none()

    if task is None:
        return {
            "task_id": task_id,
            "status": "NOT_FOUND",
            "message": f"Task {task_id} not found",
        }

    return {
        "task_id": task.task_id,
        "video_id": task.video_id,
        "task_type": task.task_type,
        "status": task.status,
        "stage": task.stage,
        "progress": task.progress,
        "created_at": task.created_at.isoformat() if task.created_at else None,
        "started_at": task.started_at.isoformat() if task.started_at else None,
        "finished_at": task.finished_at.isoformat() if task.finished_at else None,
        "error_code": task.error_code,
        "error_message": task.error_message,
        "celery_task_id": task.celery_task_id,
    }


async def get_video_results(video_id: str, db) -> dict:
    """Get all results + artifacts for a video."""
    from sqlalchemy import select

    from core.database.models import Artifact, Shot, Task, Video

    # Video
    result = await db.execute(select(Video).where(Video.video_id == video_id))
    video = result.scalar_one_or_none()
    if video is None:
        return {"video_id": video_id, "status": "NOT_FOUND"}

    # Shots
    result = await db.execute(select(Shot).where(Shot.video_id == video_id).order_by(Shot.index))
    shots = result.scalars().all()

    # Artifacts
    result = await db.execute(select(Artifact).where(Artifact.video_id == video_id))
    artifacts = result.scalars().all()

    # Latest task
    result = await db.execute(
        select(Task).where(Task.video_id == video_id).order_by(Task.created_at.desc()).limit(1)
    )
    task = result.scalar_one_or_none()

    return {
        "video_id": video_id,
        "project_id": video.project_id,
        "source_uri": video.source_uri,
        "normalized_uri": video.normalized_uri,
        "duration_ms": video.duration_ms,
        "fps_num": video.fps_num,
        "fps_den": video.fps_den,
        "width": video.width,
        "height": video.height,
        "task": {
            "task_id": task.task_id if task else None,
            "status": task.status if task else None,
            "stage": task.stage if task else None,
            "progress": task.progress if task else 0,
        }
        if task
        else None,
        "shots": [
            {
                "shot_id": s.shot_id,
                "index": s.index,
                "start_ms": s.start_ms,
                "end_ms": s.end_ms,
                "boundary_type": s.boundary_type,
                "confidence": s.confidence,
            }
            for s in shots
        ],
        "artifacts": [
            {
                "artifact_id": a.artifact_id,
                "artifact_type": a.artifact_type,
                "uri": a.uri,
                "format": a.format,
                "sha256": a.sha256,
            }
            for a in artifacts
        ],
    }
