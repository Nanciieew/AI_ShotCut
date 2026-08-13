"""Run full pipeline on Test1.mp4 → data/projects/tests/test1/"""

import json
import os
import sys
import time
import uuid
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

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

storage_root = os.getenv("STORAGE_ROOT", "./data")
project_id = "tests"
video_id = "test1"
task_id = uuid.uuid4().hex[:16]

source_path = os.path.join(storage_root, "projects/tests/test1/source/Test1.mp4")
source_uri = f"storage://projects/{project_id}/videos/{video_id}/source/Test1.mp4"
artifact_base = f"projects/{project_id}/videos/{video_id}/artifacts"

print(f"Video ID: {video_id}, Task ID: {task_id}")
print(f"Source: {source_path}")

# Step 1: Build 320×180 proxy
print("\n[1/7] Building 320×180 proxy...")
t0 = time.monotonic()
from core.media.ffmpeg import build_shot_proxy_command, run_ffmpeg
from core.media.ffprobe import run_ffprobe

proxy_dir = Path(storage_root) / artifact_base / "video_normalization" / "1.0.0"
proxy_dir.mkdir(parents=True, exist_ok=True)
proxy_path = proxy_dir / "shot_proxy_320x180.mp4"

if proxy_path.exists() and os.path.getsize(str(proxy_path)) > 100000:
    print("  (skipped — already exists)")
    probe_after = run_ffprobe(str(proxy_path))
else:
    if proxy_path.exists():
        os.remove(str(proxy_path))
    probe_before = run_ffprobe(source_path)
    cmd = build_shot_proxy_command(
        input_path=source_path,
        output_path=str(proxy_path),
        probe=probe_before,
    )
    run_ffmpeg(cmd, timeout=3600, description="build_shot_proxy")
    probe_after = run_ffprobe(str(proxy_path))

normalized_path = proxy_path
nrml_uri = f"storage://{artifact_base}/video_normalization/1.0.0/shot_proxy_320x180.mp4"
print(
    f"  {probe_after.duration_ms}ms, {probe_after.width}x{probe_after.height}, {time.monotonic() - t0:.1f}s"
)

# Step 2: Shot detection
print("\n[2/7] Detecting shots...")
t0 = time.monotonic()
shot_dir = Path(storage_root) / artifact_base / "ffmpeg_scene" / "0.1.0"
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
print(f"  {len(shots_list)} shots, {time.monotonic() - t0:.1f}s")

# Step 3+4: Keyframes ∥ Subtitle
print("\n[3/7] Extracting keyframes...")
print("[4/7] Transcribing subtitles (Doubao SeedASR)...")
t0 = time.monotonic()
from core.media.keyframes import compute_keyframe_targets, extract_keyframes

kf_proxy = Path(storage_root) / artifact_base / "shot_keyframes_proxy" / "1.0.0"
kf_proxy.mkdir(parents=True, exist_ok=True)

subtitle_segments = []
with ThreadPoolExecutor(max_workers=2) as pool:
    try:
        kf_targets = compute_keyframe_targets(shots_list, probe_after.fps_num, probe_after.fps_den)
        kf_future = pool.submit(
            lambda: extract_keyframes(
                str(normalized_path), kf_targets, kf_proxy, max_long_side=320, quality=85
            )
        )
    except Exception as e:
        print(f"  Keyframes setup FAILED: {e}")
        kf_future = None

    try:
        from models.doubao_asr.adapter import DoubaoASRAdapter

        da = DoubaoASRAdapter()
        da.load()
        sub_future = pool.submit(
            lambda: da.predict(
                {
                    "task_id": task_id,
                    "video_id": video_id,
                    "model": {"name": "doubao_asr", "version": "1.0.0"},
                    "input": {"video_uri": nrml_uri},
                    "parameters": {"language": "zh-CN"},
                }
            )
        )
        subtitle_result = sub_future.result()
        subtitle_segments = subtitle_result.get("artifacts", {}).get("subtitle_segments", [])
        print(f"  Subtitles: {len(subtitle_segments)} segments")
    except Exception as e:
        print(f"  Subtitles FAILED: {e}")

    if kf_future:
        try:
            kf_future.result()
            kf_count = len(list(kf_proxy.iterdir())) if kf_proxy.exists() else 0
            print(f"  Keyframes: {kf_count} files, {time.monotonic() - t0:.1f}s")
        except Exception as e:
            print(f"  Keyframes FAILED: {e}")

# Save subtitles
sub_dir = Path(storage_root) / artifact_base / "doubao_asr" / "1.0.0"
sub_dir.mkdir(parents=True, exist_ok=True)
with open(sub_dir / "subtitles.json", "w", encoding="utf-8") as f:
    json.dump({"subtitle_segments": subtitle_segments}, f, ensure_ascii=False)

# Step 5+6: VLM ∥ Plot
print("\n[5/7] Scoring VLM (Qwen VL)...")
print("[6/7] Scoring subtitle semantics (DeepSeek)...")
t0 = time.monotonic()
vlm_scores, subtitle_scores = [], []
vlm_dir = Path(storage_root) / artifact_base / "vlm_boundary" / "0.1.0"
vlm_scores_path = vlm_dir / "location_character_scores.json"
subtitle_dir = Path(storage_root) / artifact_base / "subtitle_semantic" / "1.0.0"
subtitle_scores_path = subtitle_dir / "subtitle_continuity.json"

with ThreadPoolExecutor(max_workers=2) as pool:
    vlm_future = None
    if len(shots_list) >= 2:
        if vlm_scores_path.exists():
            with open(vlm_scores_path) as f:
                vlm_scores = json.load(f).get("scores", [])
        else:
            from models.doubao_vision.adapter import DoubaoVisionAdapter

            def run_vlm():
                va = DoubaoVisionAdapter()
                va.load()
                va.predict(
                    {
                        "task_id": task_id,
                        "video_id": video_id,
                        "model": {"name": "doubao_vision", "version": "1.0.0"},
                        "input": {
                            "shots_uri": f"storage://{artifact_base}/ffmpeg_scene/0.1.0/shots.json",
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

    subtitle_future = None
    if subtitle_segments:
        if subtitle_scores_path.exists():
            with open(subtitle_scores_path) as f:
                subtitle_scores = json.load(f).get("boundaries", [])
        else:

            def run_subtitle_semantics():
                from models.subtitle_semantic.adapter import SubtitleSemanticAdapter

                adapter = SubtitleSemanticAdapter()
                adapter.load()
                adapter.predict(
                    {
                        "task_id": task_id,
                        "video_id": video_id,
                        "model": {"name": "subtitle_semantic", "version": "1.0.0"},
                        "input": {
                            "subtitle_segments": subtitle_segments,
                            "shots": shots_list,
                        },
                        "parameters": {},
                    }
                )
                return adapter._last_result

            subtitle_future = pool.submit(run_subtitle_semantics)

    if vlm_future:
        try:
            vlm_scores = vlm_future.result()
        except Exception as e:
            print(f"  VLM FAILED: {e}")
    if subtitle_future:
        try:
            last = subtitle_future.result()
            subtitle_scores = last.get("boundaries", [])
            subtitle_dir.mkdir(parents=True, exist_ok=True)
            with open(subtitle_scores_path, "w") as f:
                json.dump(last, f, ensure_ascii=False)
        except Exception as e:
            print(f"  Subtitle semantics FAILED: {e}")

print(
    f"  VLM: {len(vlm_scores)} scores, Subtitle: {len(subtitle_scores)} scores, "
    f"{time.monotonic() - t0:.1f}s"
)

# Step 7: Merge
print("\n[7/7] Merging scores → final scenes...")
t0 = time.monotonic()

score_mode = "location_only"
location_weight, character_weight, subtitle_weight = 1, 1, 1
cut_intensity = "medium"
min_distance_s = 12

from apps.api.services.workflow_service import _score_weights, _weighted_change

w = _score_weights(score_mode, location_weight, character_weight, subtitle_weight)

intensity_map = {"high": 0.06, "medium": 0.04, "low": 0.01}
target_count = max(3, int(len(shots_list) * intensity_map.get(cut_intensity, 0.04)))
min_dist = min_distance_s * 1000

vlm_map = {s["shot_id"]: s for s in vlm_scores}
subtitle_map = {item["shot_id"]: item for item in subtitle_scores}
merged = []
for i, shot in enumerate(shots_list[:-1]):
    sid = shot["shot_id"]
    q = vlm_map.get(sid, {})
    subtitle_continuity = subtitle_map.get(sid, {}).get("subtitle_continuity")
    scene_score = round(
        _weighted_change(
            {
                "location": q.get("location_change", 0) / 100,
                "character": q.get("character_group_change", 0) / 100,
                "subtitle": 1 - subtitle_continuity if subtitle_continuity is not None else None,
            },
            w,
        ),
        4,
    )
    merged.append(
        {
            "shot_id": sid,
            "boundary_index": i,
            "timestamp_ms": shot["end_ms"],
            "location_change": q.get("location_change", 0),
            "character_group_change": q.get("character_group_change", 0),
            "subtitle_continuity": subtitle_continuity,
            "scene_score": scene_score,
        }
    )

ranked = sorted(merged, key=lambda b: b["scene_score"], reverse=True)
selected = []
for b in ranked:
    if b["scene_score"] == 0:
        continue
    if any(abs(b["timestamp_ms"] - s["timestamp_ms"]) < min_dist for s in selected):
        continue
    selected.append(b)
    if len(selected) >= target_count:
        break
selected.sort(key=lambda b: b["timestamp_ms"])

candidate_boundaries = []
for s in selected:
    m, sec = divmod(s["timestamp_ms"], 60000)
    candidate_boundaries.append(
        {
            "shot_id": s["shot_id"],
            "boundary_index": s["boundary_index"],
            "timestamp_ms": s["timestamp_ms"],
            "timestamp_readable": f"{int(m):02d}:{sec / 1000:05.2f}",
            "scene_score": s["scene_score"],
            "location_change": s["location_change"],
            "character_group_change": s["character_group_change"],
            "subtitle_continuity": s["subtitle_continuity"],
        }
    )

final_scenes = []
scene_start, scene_start_shot = shots_list[0]["start_ms"], shots_list[0]["shot_id"]
for b in selected:
    final_scenes.append(
        {
            "start_shot": scene_start_shot,
            "end_shot": b["shot_id"],
            "start_ms": scene_start,
            "end_ms": b["timestamp_ms"],
            "scene_score": b["scene_score"],
        }
    )
    ni = b["boundary_index"] + 1
    scene_start = shots_list[ni]["start_ms"] if ni < len(shots_list) else b["timestamp_ms"]
    scene_start_shot = shots_list[ni]["shot_id"] if ni < len(shots_list) else b["shot_id"]
final_scenes.append(
    {
        "start_shot": scene_start_shot,
        "end_shot": shots_list[-1]["shot_id"],
        "start_ms": scene_start,
        "end_ms": shots_list[-1]["end_ms"],
        "scene_score": 0,
    }
)

merge_dir = Path(storage_root) / artifact_base / "scene_merger" / "1.0.0"
merge_dir.mkdir(parents=True, exist_ok=True)
final_result = {
    "video_id": video_id,
    "task_id": task_id,
    "shots": shots_list,
    "subtitle_segments": subtitle_segments,
    "scenes": final_scenes,
    "candidate_boundaries": candidate_boundaries,
    "config": {
        "mode": score_mode,
        "weights": w,
        "intensity": cut_intensity,
        "target_count": target_count,
        "min_distance_ms": min_dist,
    },
}
with open(merge_dir / "final_result.json", "w", encoding="utf-8") as f:
    json.dump(final_result, f, ensure_ascii=False, indent=2)

print(f"  Scenes: {len(final_scenes)}, {time.monotonic() - t0:.1f}s")

# Summary
print(f"\n{'=' * 60}")
print("Pipeline complete! Project: tests/test1")
print(f"  Shots: {len(shots_list)}")
print(f"  Subtitles: {len(subtitle_segments)} segments")
print(f"  VLM scores: {len(vlm_scores)}")
print(f"  Subtitle continuity scores: {len(subtitle_scores)}")
print(f"  Final scenes: {len(final_scenes)}")
print(f"  Output: {merge_dir / 'final_result.json'}")
print(f"{'=' * 60}")
