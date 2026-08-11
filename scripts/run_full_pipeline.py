#!/usr/bin/env python3
"""Run full pipeline on Test1.mp4 directly (no API server needed).

Usage:
    python scripts/run_full_pipeline.py
"""

import json
import os
import sys
import time
import uuid
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

# Ensure project root is on sys.path
_project_root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_project_root))

# Load .env
_env_path = _project_root / ".env"
if _env_path.exists():
    with open(_env_path) as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                key, _, val = line.partition("=")
                os.environ.setdefault(key.strip(), val.strip())


def _resolve_uri(uri: str, storage_root: str) -> str:
    prefix = "storage://"
    if uri.startswith(prefix):
        return os.path.join(storage_root, uri[len(prefix) :])
    return uri


def main():
    storage_root = os.getenv("STORAGE_ROOT", "./data")
    project_id = "default"

    # Find an existing Test1.mp4
    source_path = None
    existing_videos = sorted(
        (Path(storage_root) / "projects" / project_id / "videos").iterdir(),
        key=os.path.getmtime,
        reverse=True,
    )
    for vdir in existing_videos:
        candidate = vdir / "source" / "Test1.mp4"
        if candidate.exists():
            source_path = str(candidate)
            break

    if not source_path:
        print("ERROR: No Test1.mp4 found in data/projects/default/videos/*/source/")
        sys.exit(1)

    print(f"Using source: {source_path}")

    video_id = uuid.uuid4().hex[:16]
    task_id = uuid.uuid4().hex[:16]

    # Create video directory and copy file
    vid_dir = Path(storage_root) / "projects" / project_id / "videos" / video_id / "source"
    vid_dir.mkdir(parents=True, exist_ok=True)
    dest_path = vid_dir / "Test1.mp4"
    if not dest_path.exists():
        import shutil

        shutil.copy2(source_path, dest_path)

    source_uri = f"storage://projects/{project_id}/videos/{video_id}/source/Test1.mp4"
    print(f"Video ID: {video_id}, Task ID: {task_id}")
    print(f"Source URI: {source_uri}")

    # Pipeline steps
    artifact_base = f"projects/{project_id}/videos/{video_id}/artifacts"
    video_path_full = dest_path  # Already resolved above

    # Step 1: Normalize
    print("\n[1/5] Normalizing video...")
    t0 = time.monotonic()
    from core.media.ffmpeg import build_normalize_command, run_ffmpeg
    from core.media.ffprobe import run_ffprobe
    from core.media.normalization import validate_normalization
    from core.media.schemas import NormalizationConfig

    norm_dir = Path(storage_root) / artifact_base / "video_normalization" / "1.0.0"
    norm_dir.mkdir(parents=True, exist_ok=True)
    normalized_path = norm_dir / "normalized.mp4"

    if not normalized_path.exists():
        probe_before = run_ffprobe(str(video_path_full))
        cfg = NormalizationConfig()
        cmd = build_normalize_command(
            input_path=str(video_path_full),
            output_path=str(normalized_path),
            probe=probe_before,
            config=cfg,
        )
        run_ffmpeg(cmd, timeout=3600, description="normalize")
        probe_after = run_ffprobe(str(normalized_path))
        validate_normalization(
            probe_before=probe_before,
            probe_after=probe_after,
            output_path=str(normalized_path),
        )
    else:
        probe_after = run_ffprobe(str(normalized_path))

    nrml_uri = f"storage://{artifact_base}/video_normalization/1.0.0/normalized.mp4"
    print(
        f"  Normalized: {normalized_path} ({probe_after.duration_ms}ms, {probe_after.width}x{probe_after.height})"
    )
    print(f"  Time: {time.monotonic() - t0:.1f}s")

    # Step 2: Shot detection
    print("\n[2/5] Detecting shots...")
    t0 = time.monotonic()
    shot_dir = Path(storage_root) / artifact_base / "omnishotcut" / "0.1.0"
    shots_json = shot_dir / "shots.json"
    from models.ffmpeg_scene.adapter import FFmpegSceneAdapter

    adapter = FFmpegSceneAdapter()
    if shots_json.exists():
        with open(shots_json) as f:
            adapter._last_result = json.load(f)
    else:
        adapter.predict(
            {
                "task_id": task_id,
                "video_id": video_id,
                "model": {"name": "ffmpeg_scene", "version": "0.1.0"},
                "input": {"video_uri": nrml_uri},
                "parameters": {"threshold": 0.1},
            }
        )
        shot_dir.mkdir(parents=True, exist_ok=True)
        with open(shots_json, "w") as f:
            json.dump(adapter._last_result, f)

    shots_list = adapter._last_result.get("shots", [])
    print(f"  Found {len(shots_list)} shots")
    print(f"  Time: {time.monotonic() - t0:.1f}s")

    # Step 3: Keyframes + Subtitles (parallel)
    print("\n[3/5] Extracting keyframes + transcribing subtitles...")
    t0 = time.monotonic()
    from core.media.keyframes import compute_keyframe_targets, extract_keyframes

    kf_proxy = Path(storage_root) / artifact_base / "shot_keyframes_proxy" / "1.0.0"
    kf_proxy.mkdir(parents=True, exist_ok=True)

    subtitle_segments = []  # Whisper/Doubao ASR removed — not needed currently
    with ThreadPoolExecutor(max_workers=2) as pool:
        kf_future = pool.submit(
            lambda: extract_keyframes(
                str(normalized_path),
                compute_keyframe_targets(shots_list, probe_after.fps_num, probe_after.fps_den),
                kf_proxy,
                max_long_side=320,
                quality=85,
            )
        )

        # WhisperAdapter / Doubao ASR removed — subtitle step skipped
        # subtitle_segments remains empty; plot scoring will be skipped

        kf_future.result()
        print(f"  Keyframes: extracted to {kf_proxy}")

    print(f"  Time: {time.monotonic() - t0:.1f}s")

    # Step 4: VLM + Plot scoring (parallel)
    print("\n[4/5] Scoring scenes (VLM + LLM plot)...")
    t0 = time.monotonic()
    vlm_scores = []
    plot_scores = []
    vlm_dir = Path(storage_root) / artifact_base / "vlm_boundary" / "0.1.0"
    vlm_scores_path = vlm_dir / "location_character_scores.json"
    plot_dir = Path(storage_root) / artifact_base / "deepseek_plot" / "1.0.0"
    plot_scores_path = plot_dir / "plot_scores.json"

    with ThreadPoolExecutor(max_workers=2) as pool:
        vlm_future = None
        if len(shots_list) >= 2:
            if vlm_scores_path.exists():
                with open(vlm_scores_path) as f:
                    vlm_scores = json.load(f).get("scores", [])
            else:
                from models.vlm_boundary.adapter import VLMSceneBoundaryAdapter

                def run_vlm():
                    va = VLMSceneBoundaryAdapter()
                    va.load()
                    va.predict(
                        {
                            "task_id": task_id,
                            "video_id": video_id,
                            "model": {"name": "vlm_scene_boundary", "version": "0.1.0"},
                            "input": {
                                "shots_uri": f"storage://{artifact_base}/omnishotcut/0.1.0/shots.json",
                                "keyframes_dir": str(kf_proxy),
                            },
                            "parameters": {},
                        }
                    )
                    scores = va._last_result.get("scores", [])
                    vlm_dir.mkdir(parents=True, exist_ok=True)
                    with open(vlm_scores_path, "w") as f:
                        json.dump({"scores": scores}, f)
                    return scores

                vlm_future = pool.submit(run_vlm)

        plot_future = None
        if subtitle_segments:
            if plot_scores_path.exists():
                with open(plot_scores_path) as f:
                    plot_scores = json.load(f).get("plot_scores", [])
            else:
                from models.vlm_boundary.providers.deepseek_llm import DeepSeekLLMProvider

                api_key = os.getenv("QWEN_VL_API_KEY", "")
                if api_key:
                    dp = DeepSeekLLMProvider(api_key=api_key)
                    sub_lines = [
                        f"[{int(s['start_ms'] // 60000):02d}:{(s['start_ms'] % 60000) / 1000:05.2f}] {s['text'][:80]}"
                        for s in subtitle_segments
                    ]
                    dprompt = (
                        "你是电影情节分析助手。以下是电影字幕时间线。"
                        "请规划叙事事件（大/中/小三层）。"
                        "大事件(major)：类似剧本的'幕'。"
                        "中事件(medium)：大事件内的阶段。"
                        "小事件(minor)：中事件内的节拍。"
                        "每个事件输出label,level,time_range(起止ms)。"
                        '只输出JSON：{"events":[{"label":"...","level":"major",'
                        '"time_range":{"start_ms":0,"end_ms":600000}}]}\n---\n'
                        + "\n".join(sub_lines)
                    )

                    def run_plot():
                        resp = dp.send(
                            [{"role": "user", "content": dprompt}], max_tokens=4096, timeout=600
                        )
                        import re as _re

                        try:
                            events = json.loads(resp).get("events", [])
                        except json.JSONDecodeError:
                            m = _re.search(r'\{[\s\S]*"events"[\s\S]*\}', resp)
                            events = json.loads(m.group()).get("events", []) if m else []
                        level_score = {"major": 100, "medium": 60, "minor": 30}
                        scores = []
                        for i, shot in enumerate(shots_list[:-1]):
                            boundary_ms = shot["end_ms"]
                            max_score = 0
                            for evt in events:
                                tr = evt.get("time_range", {})
                                evt_start = tr.get("start_ms", 0)
                                evt_end = tr.get("end_ms", 0)
                                if (
                                    evt_start <= boundary_ms <= evt_end
                                    or abs(boundary_ms - evt_start) < 2000
                                ):
                                    score = level_score.get(evt.get("level", "minor"), 30)
                                    if score > max_score:
                                        max_score = score
                            scores.append(
                                {
                                    "shot_id": shot["shot_id"],
                                    "boundary_index": i,
                                    "timestamp_ms": boundary_ms,
                                    "plot_change_score": max_score / 100.0,
                                }
                            )
                        plot_dir.mkdir(parents=True, exist_ok=True)
                        with open(plot_scores_path, "w") as f:
                            json.dump({"plot_scores": scores}, f)
                        return scores

                    plot_future = pool.submit(run_plot)

        if vlm_future:
            try:
                vlm_scores = vlm_future.result()
                print(f"  VLM: {len(vlm_scores)} boundary scores")
            except Exception as e:
                print(f"  VLM FAILED: {e}")
        if plot_future:
            try:
                plot_scores = plot_future.result()
                print(f"  Plot: {len(plot_scores)} boundary scores")
            except Exception as e:
                print(f"  Plot FAILED: {e}")

    print(f"  Time: {time.monotonic() - t0:.1f}s")

    # Step 5: Merge scores → final scenes
    print("\n[5/5] Merging scores → final scenes...")
    t0 = time.monotonic()

    if not vlm_scores:
        vlm_scores_dict = {}
    else:
        vlm_scores_dict = {s["shot_id"]: s for s in vlm_scores}
    if not plot_scores:
        plot_by_shot = {}
    else:
        plot_by_shot = {p["shot_id"]: p for p in plot_scores}

    # Weights (location_only)
    w = (1.0, 0.0, 0.0)
    intensity_ratios = {"high": 0.06, "medium": 0.04, "low": 0.01}
    min_distance_ms = 12 * 1000
    intensity = "medium"

    merged = []
    for i, shot in enumerate(shots_list[:-1]):
        sid = shot["shot_id"]
        q = vlm_scores_dict.get(sid, {})
        loc = q.get("location_change", 0)
        char = q.get("character_group_change", 0)
        p = plot_by_shot.get(sid, {})
        plot = p.get("plot_change", p.get("plot_change_score", 0))
        scene_score = round(w[0] * loc + w[1] * char + w[2] * plot)
        merged.append(
            {
                "shot_id": sid,
                "boundary_index": i,
                "timestamp_ms": shot["end_ms"],
                "scene_score": scene_score,
                "location_change": loc,
                "character_group_change": char,
                "plot_change_score": plot,
            }
        )

    # Greedy selection
    merged.sort(key=lambda x: x["scene_score"], reverse=True)
    target_count = max(3, int(len(shots_list) * intensity_ratios[intensity]))
    selected = []
    for b in merged:
        if len(selected) >= target_count:
            break
        if any(abs(b["timestamp_ms"] - s["timestamp_ms"]) < min_distance_ms for s in selected):
            continue
        selected.append(b)
    selected.sort(key=lambda x: x["boundary_index"])

    # Build final scenes
    final_scenes = []
    scene_start_ms = 0
    scene_start_shot = shots_list[0]["shot_id"]
    next_idx = 0
    for b in selected:
        final_scenes.append(
            {
                "start_shot": scene_start_shot,
                "end_shot": b["shot_id"],
                "start_ms": scene_start_ms,
                "end_ms": b["timestamp_ms"],
                "scene_score": b["scene_score"],
            }
        )
        next_idx = b["boundary_index"] + 1
        scene_start_ms = (
            shots_list[next_idx]["start_ms"] if next_idx < len(shots_list) else b["timestamp_ms"]
        )
        scene_start_shot = (
            shots_list[next_idx]["shot_id"] if next_idx < len(shots_list) else b["shot_id"]
        )
    final_scenes.append(
        {
            "start_shot": scene_start_shot,
            "end_shot": shots_list[-1]["shot_id"],
            "start_ms": scene_start_ms,
            "end_ms": shots_list[-1]["end_ms"],
            "scene_score": 0,
        }
    )

    final_dir = Path(storage_root) / artifact_base / "final" / "1.0.0"
    final_dir.mkdir(parents=True, exist_ok=True)
    final_result = {
        "video_id": video_id,
        "task_id": task_id,
        "shots": shots_list,
        "subtitle_segments": subtitle_segments,
        "scenes": final_scenes,
        "candidate_boundaries": merged,
        "config": {
            "mode": "location_only",
            "weights": {"location": w[0], "character": w[1], "plot": w[2]},
            "intensity": intensity,
            "target_count": target_count,
            "min_distance_ms": min_distance_ms,
        },
    }
    output_path = final_dir / "final_result.json"
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(final_result, f, ensure_ascii=False, indent=2)

    print(f"  Final scenes: {len(final_scenes)}")
    print(f"  Output: {output_path}")
    print(f"  Time: {time.monotonic() - t0:.1f}s")

    # Summary
    print(f"\n{'=' * 60}")
    print("Pipeline complete!")
    print(f"  Video: {video_id}")
    print(f"  Shots: {len(shots_list)}")
    print(f"  Subtitles: {len(subtitle_segments)} segments")
    print(f"  Scenes: {len(final_scenes)}")
    print(f"  Output: {output_path}")
    print(f"{'=' * 60}")


if __name__ == "__main__":
    main()
