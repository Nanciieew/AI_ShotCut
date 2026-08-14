"""WorkflowService — process-inline Python Executor.

Each step: ModelRun(RUNNING) → Adapter → Artifact → ModelRun(SUCCEEDED).
Creates WorkflowRun record on pipeline start/end.
"""

import json
import os
import time
import uuid
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from apps.api.services.artifact_service import ArtifactService
from apps.api.services.cache_service import (
    CacheHit,
    WorkflowCacheService,
    canonical_cache_key,
    hash_file,
    hash_json,
)
from apps.api.services.scene_service import assemble_scenes
from core.database.models import (
    Artifact,
    CandidateBoundary,
    ModelRun,
    ModelRunInput,
    ModelRunOutput,
    Scene,
    SceneEvidence,
    Task,
    WorkflowRun,
)
from core.database.repositories import TaskRepository
from core.database.session_sync import get_sync_session
from core.media.ffmpeg import build_normalize_command, run_ffmpeg
from core.media.ffprobe import run_ffprobe
from core.media.normalization import validate_normalization
from schemas.scene import CandidateBoundary as CandidateBoundarySchema

_INTENSITY_RATIOS = {"high": 0.06, "medium": 0.04, "low": 0.01}


class WorkflowStepError(RuntimeError):
    def __init__(self, error: dict) -> None:
        super().__init__(str(error))
        self.error = error
        self.retryable = bool(error.get("retryable", False))


def _new_id() -> str:
    return uuid.uuid4().hex


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _mark_run_succeeded(model_run: ModelRun, *, runtime_ms: int | None = None) -> None:
    """Close a ModelRun and persist input-to-return wall time."""
    finished = _now()
    model_run.status = "SUCCEEDED"
    model_run.finished_at = finished
    if runtime_ms is not None:
        model_run.runtime_ms = max(0, runtime_ms)
    elif model_run.started_at is not None:
        comparable_finished = finished
        if model_run.started_at.tzinfo is None:
            comparable_finished = finished.replace(tzinfo=None)
        model_run.runtime_ms = max(
            0,
            int((comparable_finished - model_run.started_at).total_seconds() * 1000),
        )


def _score_weights(
    mode: str,
    location_weight: int,
    character_weight: int,
    subtitle_weight: int = 0,
) -> dict[str, float]:
    """Return normalized evidence weights whose sum is exactly 1."""
    if mode == "character_only":
        return {"location": 0.0, "character": 1.0, "subtitle": 0.0}
    if mode == "subtitle_only":
        return {"location": 0.0, "character": 0.0, "subtitle": 1.0}
    if mode == "location_only":
        return {"location": 1.0, "character": 0.0, "subtitle": 0.0}
    if mode != "custom":
        raise ValueError(f"Unsupported score mode: {mode}")

    location = max(0, location_weight)
    character = max(0, character_weight)
    subtitle = max(0, subtitle_weight)
    total = location + character + subtitle
    if total == 0:
        raise ValueError("Custom score weights must contain at least one non-zero value")
    return {
        "location": location / total,
        "character": character / total,
        "subtitle": subtitle / total,
    }


def _pipeline_requirements(
    scene_analysis: bool,
    mode: str,
    location_weight: int,
    character_weight: int,
    subtitle_weight: int,
) -> tuple[dict[str, float], bool, bool]:
    """Resolve score weights and the only provider branches the task needs."""
    if not scene_analysis:
        return {"location": 0.0, "character": 0.0, "subtitle": 0.0}, False, False
    weights = _score_weights(
        mode,
        location_weight,
        character_weight,
        subtitle_weight,
    )
    needs_visual = weights["location"] > 0 or weights["character"] > 0
    needs_subtitle = weights["subtitle"] > 0
    return weights, needs_visual, needs_subtitle


def _weighted_change(changes: dict[str, float | None], weights: dict[str, float]) -> float:
    """Combine required evidence without silently changing requested weights."""
    required = {name for name, weight in weights.items() if weight > 0}
    missing = sorted(name for name in required if changes.get(name) is None)
    if missing:
        raise ValueError(f"Required scene evidence missing: {', '.join(missing)}")
    total = 0.0
    for name in required:
        value = changes[name]
        if value is None:  # Narrow the type after the aggregate validation above.
            raise ValueError(f"Required scene evidence missing: {name}")
        total += min(1.0, max(0.0, value)) * weights[name]
    return total


def _canonicalize_shots(shots: list[dict], video_id: str) -> list[dict]:
    """Replace adapter-local labels with globally unique, stable downstream IDs."""
    for index, shot in enumerate(shots):
        shot["shot_id"] = _new_id()
        shot["video_id"] = video_id
        shot["index"] = index
    return shots


def _shot_timeline(shots: list[dict]) -> list[dict]:
    """Return the task-ID-independent portion of a Shot Artifact."""
    return [
        {
            "index": index,
            "start_ms": int(shot["start_ms"]),
            "end_ms": int(shot["end_ms"]),
            "start_frame": shot.get("start_frame"),
            "end_frame_exclusive": shot.get("end_frame_exclusive"),
        }
        for index, shot in enumerate(shots)
    ]


def _subtitle_content(segments: list[dict]) -> list[dict]:
    """Return ASR meaning and timing without task-scoped identifiers."""
    return [
        {
            "start_ms": int(item.get("start_ms", 0)),
            "end_ms": int(item.get("end_ms", 0)),
            "text": str(item.get("text", "")),
            "language": item.get("language"),
            "confidence": item.get("confidence"),
        }
        for item in segments
    ]


def _remap_cached_keyframes(current_shots: list[dict], cached_data: dict) -> dict | None:
    cached_items = cached_data.get("shots", [])
    if len(cached_items) != len(current_shots):
        return None
    remapped: list[dict] = []
    for index, (shot, item) in enumerate(zip(current_shots, cached_items, strict=True)):
        if int(item.get("start_ms", -1)) != int(shot["start_ms"]) or int(
            item.get("end_ms", -1)
        ) != int(shot["end_ms"]):
            return None
        remapped.append(
            {
                **item,
                "shot_id": str(shot["shot_id"]),
                "index": index,
                "start_ms": int(shot["start_ms"]),
                "end_ms": int(shot["end_ms"]),
            }
        )
    return {**cached_data, "shots": remapped}


def _remap_cached_vision_scores(
    current_shots: list[dict],
    cached_shots: list[dict],
    cached_scores: list[dict],
) -> list[dict] | None:
    """Reuse Vision only when the ordered shot timeline is exactly identical."""
    current_timeline = [(int(shot["start_ms"]), int(shot["end_ms"])) for shot in current_shots]
    cached_timeline = [(int(shot["start_ms"]), int(shot["end_ms"])) for shot in cached_shots]
    if current_timeline != cached_timeline or len(cached_scores) != max(0, len(current_shots) - 1):
        return None
    remapped = []
    for index, score in enumerate(cached_scores):
        remapped.append({**score, "shot_id": str(current_shots[index]["shot_id"])})
    return remapped


def _remap_cached_subtitle_continuity(
    current_shots: list[dict],
    cached_shots: list[dict],
    cached_data: dict,
) -> dict | None:
    """Remap sparse subtitle evidence to new globally unique Shot IDs."""
    current_timeline = [(int(shot["start_ms"]), int(shot["end_ms"])) for shot in current_shots]
    cached_timeline = [(int(shot["start_ms"]), int(shot["end_ms"])) for shot in cached_shots]
    if current_timeline != cached_timeline:
        return None
    remapped = []
    for item in cached_data.get("boundaries", []):
        index = int(item["boundary_index"])
        if index < 0 or index >= len(current_shots) - 1:
            return None
        remapped.append(
            {
                **item,
                "shot_id": str(current_shots[index]["shot_id"]),
                "timestamp_ms": int(current_shots[index]["end_ms"]),
            }
        )
    return {**cached_data, "boundaries": remapped}


def _select_boundaries(
    boundaries: list[dict],
    *,
    min_distance_ms: int,
    target_count: int,
) -> list[dict]:
    """Select strongest boundaries first, then enforce temporal separation."""
    if target_count <= 0:
        return []
    ranked = sorted(boundaries, key=lambda boundary: boundary["scene_score"], reverse=True)
    selected: list[dict] = []
    for boundary in ranked:
        if boundary["scene_score"] <= 0:
            continue
        if any(
            abs(boundary["timestamp_ms"] - chosen["timestamp_ms"]) < min_distance_ms
            for chosen in selected
        ):
            continue
        selected.append(boundary)
        if len(selected) >= target_count:
            break
    return sorted(selected, key=lambda boundary: boundary["timestamp_ms"])


class WorkflowService:
    def __init__(self, artifact_svc: ArtifactService):
        self.a = artifact_svc
        self.cache = WorkflowCacheService(artifact_svc.storage)

    # ------------------------------------------------------------------
    # Public entry point
    # ------------------------------------------------------------------

    def run_pipeline(
        self,
        *,
        project_id: str,
        task_id: str,
        video_id: str,
        scene_analysis: bool = True,
        min_distance_s: int = 12,
        score_mode: str = "location_only",
        location_weight: int = 1,
        character_weight: int = 1,
        subtitle_weight: int = 1,
        cut_intensity: str = "medium",
        force_recompute: list[str] | None = None,
    ) -> dict:
        pid, tid, vid = project_id, task_id, video_id
        wf_run_id = _new_id()
        t0 = time.monotonic()
        forced = set(force_recompute or [])

        # Create WorkflowRun + link to Task
        with get_sync_session() as s:
            s.add(
                WorkflowRun(
                    workflow_run_id=wf_run_id,
                    task_id=tid,
                    workflow_name="video_analysis",
                    workflow_version="1.0.0",
                    status="RUNNING",
                    started_at=_now(),
                )
            )
            task = s.get(Task, tid)
            if task:
                task.workflow_run_id = wf_run_id
            s.commit()

        try:
            weights, needs_visual, needs_subtitle = _pipeline_requirements(
                scene_analysis,
                score_mode,
                location_weight,
                character_weight,
                subtitle_weight,
            )

            self._update_status(tid, "RUNNING", "normalize_video", 5)
            norm_outputs = self._normalize(
                pid,
                tid,
                vid,
                extract_audio=needs_subtitle,
                use_cache="normalize" not in forced,
            )
            shot_outputs = self._detect_shots(
                pid,
                tid,
                vid,
                normalized_video_artifact_id=norm_outputs["normalized_video_artifact_id"],
                use_cache="shots" not in forced,
            )
            shots = shot_outputs["shots"]

            if scene_analysis:
                keyframes_artifact_id = None
                vision_artifact_id = None
                subtitle_continuity_artifact_id = None

                if needs_visual:
                    keyframes_artifact_id = self._extract_keyframes(
                        pid,
                        tid,
                        vid,
                        shots,
                        shots_artifact_id=shot_outputs["artifact_id"],
                        normalized_video_artifact_id=(norm_outputs["normalized_video_artifact_id"]),
                        use_cache="keyframes" not in forced,
                    )
                    vision_artifact_id = self._score_vlm(
                        pid,
                        tid,
                        vid,
                        shots,
                        shots_artifact_id=shot_outputs["artifact_id"],
                        keyframes_artifact_id=keyframes_artifact_id,
                        use_cache="vision" not in forced,
                    )

                if needs_subtitle:
                    audio_artifact_id = norm_outputs.get("audio_artifact_id", "")
                    if not audio_artifact_id:
                        raise RuntimeError(
                            "REQUIRED_EVIDENCE_MISSING: subtitle scoring requires an audio track"
                        )
                    subtitle_artifact_id = self._transcribe(
                        pid,
                        tid,
                        vid,
                        audio_artifact_id=audio_artifact_id,
                        use_cache="asr" not in forced,
                    )
                    if not subtitle_artifact_id:
                        raise RuntimeError(
                            "REQUIRED_EVIDENCE_MISSING: ASR produced no subtitle Artifact"
                        )
                    subtitle_continuity_artifact_id = self._score_subtitle_semantics(
                        pid,
                        tid,
                        vid,
                        subtitle_artifact_id=subtitle_artifact_id,
                        shots_artifact_id=shot_outputs["artifact_id"],
                        use_cache="subtitle_semantic" not in forced,
                    )
                self._merge_scores(
                    pid,
                    tid,
                    vid,
                    score_mode,
                    location_weight,
                    character_weight,
                    subtitle_weight,
                    min_distance_s,
                    cut_intensity,
                    input_artifacts={
                        "shots": shot_outputs["artifact_id"],
                        "visual_continuity": vision_artifact_id,
                        "subtitle_continuity": subtitle_continuity_artifact_id,
                    },
                )

            runtime_ms = int((time.monotonic() - t0) * 1000)
            self._update_status(tid, "SUCCEEDED", "complete", 100)

            with get_sync_session() as s:
                wf = s.get(WorkflowRun, wf_run_id)
                if wf:
                    wf.status = "SUCCEEDED"
                    wf.finished_at = _now()
                    s.commit()

            return {"status": "SUCCEEDED", "task_id": tid, "runtime_ms": runtime_ms}

        except Exception as e:
            self._fail_running_model_runs(tid, e)
            with get_sync_session() as s:
                wf = s.get(WorkflowRun, wf_run_id)
                if wf:
                    wf.status = "FAILED"
                    wf.finished_at = _now()
                    s.commit()
            self._set_error(tid, "PIPELINE_FAILED", str(e))
            return {"status": "FAILED", "task_id": tid, "error": str(e)}

    # ------------------------------------------------------------------
    # Helper: create ModelRun before each step
    # ------------------------------------------------------------------

    def _create_run(
        self,
        task_id: str,
        video_id: str,
        model_name: str,
        model_version: str,
        *,
        cache_key: str | None = None,
        parameters: dict | None = None,
    ) -> str:
        run_id = _new_id()
        try:
            with get_sync_session() as session:
                session.add(
                    ModelRun(
                        run_id=run_id,
                        task_id=task_id,
                        video_id=video_id,
                        model_name=model_name,
                        model_version=model_version,
                        schema_version="1.0",
                        parameters_json=parameters,
                        cache_key=cache_key,
                        status="RUNNING",
                        device="cpu",
                        started_at=_now(),
                    )
                )
                session.commit()
        except IntegrityError:
            if cache_key is None:
                raise
            # A concurrent task may be producing the same key. Avoid breaking the
            # pipeline; this request computes independently without claiming origin.
            run_id = _new_id()
            collision_parameters = {**(parameters or {}), "cache_collision_bypass": True}
            with get_sync_session() as session:
                session.add(
                    ModelRun(
                        run_id=run_id,
                        task_id=task_id,
                        video_id=video_id,
                        model_name=model_name,
                        model_version=model_version,
                        schema_version="1.0",
                        parameters_json=collision_parameters,
                        cache_key=None,
                        status="RUNNING",
                        device="cpu",
                        started_at=_now(),
                    )
                )
                session.commit()

        return run_id

    # ------------------------------------------------------------------
    # Step 1: Normalize video + extract audio
    # ------------------------------------------------------------------

    def _normalize(
        self,
        pid: str,
        tid: str,
        vid: str,
        *,
        extract_audio: bool = True,
        use_cache: bool = True,
    ) -> dict:
        """Returns {audio_artifact_id, normalized_video_uri, ...}."""
        ver = "1.0.0"
        model = "ffmpeg_normalizer"

        # Find source video
        import os as _os
        from pathlib import Path as _Path

        src_path = ""
        sd = _Path(self.a.storage.source_dir(pid, vid))
        candidates = (
            list(sd.glob("*.mp4"))
            + list(sd.glob("*.mov"))
            + list(sd.glob("*.mkv"))
            + list(sd.glob("*.avi"))
        )
        if candidates:
            src_path = str(candidates[0])
        else:
            raise FileNotFoundError(f"No source video in {sd}")

        source_sha256 = hash_file(src_path)
        cache_key = canonical_cache_key(
            stage="video.normalize",
            model_name=model,
            model_version=ver,
            inputs={"video_id": vid, "source_sha256": source_sha256},
            parameters={
                "extract_audio": extract_audio,
                "video_codec": "h264",
                "audio_sample_rate": 16_000 if extract_audio else None,
                "audio_channels": 1 if extract_audio else None,
            },
            implementation="ffmpeg-normalize-contract-v2",
        )
        required_roles = {"video", "audio"} if extract_audio else {"video"}
        hit = (
            self.cache.find(
                video_id=vid,
                cache_key=cache_key,
                required_roles=required_roles,
            )
            if use_cache
            else None
        )
        if hit is None and use_cache:
            hit = self._find_reusable_normalization(
                video_id=vid,
                cache_key=cache_key,
                source_path=src_path,
                extract_audio=extract_audio,
            )
        if hit is not None:
            run_id = self._create_run(tid, vid, model, ver)
            self._record_cache_hit(run_id=run_id, hit=hit, link_cached_outputs=True)
            video_output = hit.outputs["video"]
            audio_output = hit.outputs.get("audio")
            cached_path = self.a.resolve(video_output.uri)
            cached_probe = run_ffprobe(cached_path)
            from core.database.models import Video

            with get_sync_session() as session:
                video = session.get(Video, vid)
                if video:
                    video.normalized_uri = video_output.uri
                    setattr(video, "audio_uri", audio_output.uri if audio_output else None)
                    video.duration_ms = cached_probe.duration_ms
                    video.fps_num = cached_probe.fps_num
                    video.fps_den = cached_probe.fps_den
                    video.width = cached_probe.width
                    video.height = cached_probe.height
                    if audio_output:
                        video.audio_sample_rate = 16_000
                session.commit()
            self._update_status(tid, "RUNNING", "normalize_video", 20)
            return {
                "audio_artifact_id": audio_output.artifact_id if audio_output else "",
                "normalized_video_artifact_id": video_output.artifact_id,
                "normalized_video_uri": cached_path,
            }

        run_id = self._create_run(
            tid,
            vid,
            model,
            ver,
            cache_key=cache_key,
            parameters={"extract_audio": extract_audio, "source_sha256": source_sha256},
        )

        out_dir = self.a.model_dir(pid, vid, tid, model, ver)
        video_path = out_dir + "/video.mp4"
        audio_path = out_dir + "/audio.wav"

        # --- 1a. Normalize video ---
        source_probe = run_ffprobe(src_path)
        cmd = build_normalize_command(src_path, video_path, source_probe)
        run_ffmpeg(cmd)
        norm_probe = run_ffprobe(video_path)
        errors = validate_normalization(source_probe, norm_probe, video_path)
        if errors:
            raise RuntimeError(f"Normalization failed: {'; '.join(errors)}")

        # The video normalization outputs are valid even when the source has no
        # audio stream. Persist probes before attempting optional ASR audio.
        self.a.write_artifact(
            project_id=pid,
            video_id=vid,
            task_id=tid,
            model_name=model,
            model_version=ver,
            run_id=run_id,
            filename="probe_before.json",
            data=source_probe.to_dict(),
            artifact_type="video_probe",
        )
        video_result = self.a.register_file_artifact(
            project_id=pid,
            video_id=vid,
            task_id=tid,
            model_name=model,
            model_version=ver,
            run_id=run_id,
            filename="video.mp4",
            artifact_type="video.normalized",
            format="mp4",
            mime_type="video/mp4",
            output_role="video",
            metadata={
                "duration_ms": norm_probe.duration_ms,
                "fps_num": norm_probe.fps_num,
                "fps_den": norm_probe.fps_den,
            },
        )
        self.a.write_artifact(
            project_id=pid,
            video_id=vid,
            task_id=tid,
            model_name=model,
            model_version=ver,
            run_id=run_id,
            filename="probe_after.json",
            data=norm_probe.to_dict(),
            artifact_type="video_probe",
        )

        def finish_normalize_run(audio_uri: str | None = None) -> None:
            from core.database.models import Video

            with get_sync_session() as session:
                model_run = session.get(ModelRun, run_id)
                if model_run:
                    _mark_run_succeeded(model_run)
                video = session.get(Video, vid)
                if video:
                    video.normalized_uri = video_result["uri"]
                    if audio_uri:
                        video.audio_uri = audio_uri
                    video.duration_ms = norm_probe.duration_ms
                    video.fps_num = norm_probe.fps_num
                    video.fps_den = norm_probe.fps_den
                    video.width = norm_probe.width
                    video.height = norm_probe.height
                    if audio_uri:
                        video.audio_sample_rate = 16_000
                session.commit()

        if not extract_audio:
            finish_normalize_run()
            self._update_status(tid, "RUNNING", "normalize_video", 20)
            return {
                "audio_artifact_id": "",
                "normalized_video_artifact_id": video_result["artifact_id"],
                "normalized_video_uri": video_path,
            }

        # --- 1b. Extract audio.wav for ASR ---
        from core.media.ffmpeg import build_asr_audio_command

        try:
            run_ffmpeg(build_asr_audio_command(video_path, audio_path))
        except Exception as e:
            msg = str(e)
            if "Stream map '0:a:0'" in msg or "does not contain any stream" in msg:
                logger = __import__("logging").getLogger(__name__)
                logger.warning("AUDIO_STREAM_MISSING: video %s has no audio track", vid)
                finish_normalize_run()
                self._update_status(tid, "RUNNING", "normalize_video", 20)
                return {
                    "audio_artifact_id": "",
                    "normalized_video_artifact_id": video_result["artifact_id"],
                    "normalized_video_uri": video_path,
                }
            raise RuntimeError(f"Audio extraction failed: {e}")

        if not _os.path.exists(audio_path) or _os.path.getsize(audio_path) == 0:
            finish_normalize_run()
            self._update_status(tid, "RUNNING", "normalize_video", 20)
            return {
                "audio_artifact_id": "",
                "normalized_video_artifact_id": video_result["artifact_id"],
                "normalized_video_uri": video_path,
            }

        # --- 1c. Register all artifacts with SAME run_id ---
        # Audio artifact (binary, with real artifact_id)
        audio_result = self.a.register_file_artifact(
            project_id=pid,
            video_id=vid,
            task_id=tid,
            model_name=model,
            model_version=ver,
            run_id=run_id,
            filename="audio.wav",
            artifact_type="audio.normalized",
            format="wav",
            mime_type="audio/wav",
            output_role="audio",
            metadata={
                "sample_rate": 16000,
                "channels": 1,
                "codec": "pcm_s16le",
                "duration_ms": norm_probe.duration_ms,
            },
        )

        # Mark ModelRun SUCCEEDED after all outputs
        finish_normalize_run(audio_result["uri"])

        self._update_status(tid, "RUNNING", "normalize_video", 20)
        return {
            "audio_artifact_id": audio_result["artifact_id"],
            "normalized_video_artifact_id": video_result["artifact_id"],
            "normalized_video_uri": video_path,
        }

    def _find_reusable_normalization(
        self,
        *,
        video_id: str,
        cache_key: str,
        source_path: str,
        extract_audio: bool,
    ) -> CacheHit | None:
        """One-time migration bridge for successful runs created before cache keys."""
        required = {"video", "audio"} if extract_audio else {"video"}
        with get_sync_session() as session:
            runs = list(
                session.execute(
                    select(ModelRun)
                    .where(
                        ModelRun.video_id == video_id,
                        ModelRun.model_name == "ffmpeg_normalizer",
                        ModelRun.model_version == "1.0.0",
                        ModelRun.status == "SUCCEEDED",
                    )
                    .order_by(ModelRun.finished_at.desc())
                ).scalars()
            )
            candidates = []
            for run in runs:
                rows = session.execute(
                    select(ModelRunOutput.output_role, Artifact)
                    .join(Artifact, Artifact.artifact_id == ModelRunOutput.artifact_id)
                    .where(ModelRunOutput.run_id == run.run_id)
                ).all()
                outputs = {
                    str(role): self.cache.artifact(artifact.artifact_id)
                    for role, artifact in rows
                    if role in required
                }
                if required.issubset(outputs):
                    candidates.append((run.run_id, outputs))

        source_probe = run_ffprobe(source_path)
        for source_run_id, outputs in candidates:
            try:
                for output in outputs.values():
                    path = self.a.resolve(output.uri)
                    if not os.path.isfile(path):
                        raise FileNotFoundError(path)
                    if output.sha256 and hash_file(path) != output.sha256:
                        raise ValueError("cached output checksum mismatch")
                video_path = self.a.resolve(outputs["video"].uri)
                cached_probe = run_ffprobe(video_path)
                if validate_normalization(source_probe, cached_probe, video_path):
                    continue
            except (OSError, ValueError, RuntimeError):
                continue
            self.cache.promote_legacy_run(source_run_id, cache_key)
            return CacheHit(
                source_run_id=source_run_id,
                cache_key=cache_key,
                outputs=outputs,
            )
        return None

    # ------------------------------------------------------------------
    # Step 2: Shot detection
    # ------------------------------------------------------------------

    def _detect_shots(
        self,
        pid: str,
        tid: str,
        vid: str,
        *,
        normalized_video_artifact_id: str,
        use_cache: bool = True,
    ) -> dict:
        from models.ffmpeg_scene.adapter import FFmpegSceneAdapter

        model, ver = "ffmpeg_scene", "1.0.0"
        cache_key = canonical_cache_key(
            stage="shot.detect",
            model_name=model,
            model_version=ver,
            inputs={
                "video_id": vid,
                "normalized_video": self.cache.artifact_fingerprint(normalized_video_artifact_id),
            },
            parameters={"threshold": 0.1, "min_shot_duration_ms": 500},
            implementation="ffmpeg-scene-contract-v2",
        )
        hit = (
            self.cache.find(
                video_id=vid,
                cache_key=cache_key,
                required_roles={"shots"},
            )
            if use_cache
            else None
        )
        run_id = self._create_run(
            tid,
            vid,
            model,
            ver,
            cache_key=None if hit else cache_key,
            parameters={"threshold": 0.1, "min_shot_duration_ms": 500},
        )
        if hit:
            self._record_cache_hit(
                run_id=run_id,
                hit=hit,
                input_artifact_ids={"video": normalized_video_artifact_id},
                complete=False,
            )
            with open(self.a.resolve(hit.outputs["shots"].uri), encoding="utf-8") as file:
                shots = json.load(file).get("shots", [])
            shots = _canonicalize_shots([dict(item) for item in shots], vid)
        else:
            shots = []
        with get_sync_session() as session:
            if not hit:
                session.add(
                    ModelRunInput(
                        run_id=run_id,
                        artifact_id=normalized_video_artifact_id,
                        input_role="video",
                    )
                )
            session.commit()

        if not hit:
            video_uri = self._artifact_uri(normalized_video_artifact_id)
            adapter = FFmpegSceneAdapter()
            adapter.load()
            output = adapter.predict(
                {
                    "schema_version": "1.0",
                    "task_id": tid,
                    "video_id": vid,
                    "model": {"name": model, "version": ver},
                    "input": {"video_uri": video_uri},
                    "parameters": {},
                }
            )
            if output.get("status") != "SUCCEEDED":
                raise RuntimeError(str(output.get("error", {})))
            shots = adapter._last_result.get("shots", [])
            _canonicalize_shots(shots, vid)
        if not shots:
            raise RuntimeError("No shots detected")

        artifact = self.a.write_artifact(
            project_id=pid,
            video_id=vid,
            task_id=tid,
            model_name=model,
            model_version=ver,
            run_id=run_id,
            filename="ffmpeg_scene.json",
            data={"video_id": vid, "shots": shots, "model": {"name": model}},
            artifact_type="shots",
            output_role="shots",
        )

        # Write shot DB records
        with get_sync_session() as session:
            from core.database.models import Shot

            for i, s in enumerate(shots):
                session.add(
                    Shot(
                        shot_id=s["shot_id"],
                        video_id=vid,
                        producer_run_id=run_id,
                        index=i,
                        start_ms=s.get("start_ms", 0),
                        end_ms=s.get("end_ms", 0),
                        start_frame=s.get("start_frame"),
                        end_frame_exclusive=s.get("end_frame_exclusive"),
                        boundary_type=s.get("boundary_type"),
                        confidence=s.get("confidence"),
                    )
                )
            model_run = session.get(ModelRun, run_id)
            if model_run:
                _mark_run_succeeded(model_run)
            session.commit()

        self._update_status(tid, "RUNNING", "detect_shots", 40)
        return {"shots": shots, "artifact_id": artifact["artifact_id"]}

    # ------------------------------------------------------------------
    # Step 3: Keyframe extraction
    # ------------------------------------------------------------------

    def _extract_keyframes(
        self,
        pid: str,
        tid: str,
        vid: str,
        shots: list[dict],
        *,
        shots_artifact_id: str,
        normalized_video_artifact_id: str,
        use_cache: bool = True,
    ) -> str:
        from pipelines.services.keyframe_service import run_keyframe_extraction

        model, ver = "ffmpeg_keyframes", "1.0.0"
        cache_key = canonical_cache_key(
            stage="shot.extract_keyframes",
            model_name=model,
            model_version=ver,
            inputs={
                "video_id": vid,
                "normalized_video": self.cache.artifact_fingerprint(normalized_video_artifact_id),
                "shot_timeline": hash_json(_shot_timeline(shots)),
            },
            parameters={"positions": [[1, 4], [1, 2], [3, 4]], "format": "jpeg"},
            implementation="ffmpeg-keyframes-contract-v2",
        )
        hit = (
            self.cache.find(
                video_id=vid,
                cache_key=cache_key,
                required_roles={"keyframes"},
            )
            if use_cache
            else None
        )
        run_id = self._create_run(
            tid,
            vid,
            model,
            ver,
            cache_key=None if hit else cache_key,
        )
        if hit:
            self._record_cache_hit(
                run_id=run_id,
                hit=hit,
                input_artifact_ids={
                    "shots": shots_artifact_id,
                    "video": normalized_video_artifact_id,
                },
                complete=False,
            )
            with open(self.a.resolve(hit.outputs["keyframes"].uri), encoding="utf-8") as file:
                cached_data = json.load(file)
            remapped = _remap_cached_keyframes(shots, cached_data)
            if remapped is None:
                raise RuntimeError("CACHE_CORRUPT: keyframe timeline does not match shots")
            for item in remapped.get("shots", []):
                for sample in item.get("samples", []):
                    uri = sample.get("uri")
                    if not uri or not os.path.isfile(self.a.resolve(uri)):
                        raise RuntimeError("CACHE_CORRUPT: cached keyframe image is missing")
            with get_sync_session() as session:
                artifact = self.a.write_artifact(
                    project_id=pid,
                    video_id=vid,
                    task_id=tid,
                    model_name=model,
                    model_version=ver,
                    run_id=run_id,
                    filename="keyframes.json",
                    data=remapped,
                    artifact_type="shot_keyframes",
                    output_role="keyframes",
                    db_session=session,
                )
                model_run = session.get(ModelRun, run_id)
                if model_run:
                    _mark_run_succeeded(model_run)
                session.commit()
            self._update_status(tid, "RUNNING", "extract_keyframes", 55)
            return artifact["artifact_id"]

        with get_sync_session() as session:
            session.add_all(
                [
                    ModelRunInput(
                        run_id=run_id,
                        artifact_id=shots_artifact_id,
                        input_role="shots",
                    ),
                    ModelRunInput(
                        run_id=run_id,
                        artifact_id=normalized_video_artifact_id,
                        input_role="video",
                    ),
                ]
            )
            session.commit()

        video_path = self.a.resolve(self._artifact_uri(normalized_video_artifact_id))
        probe = run_ffprobe(video_path)
        keyframes_dir = self.a.model_dir(pid, vid, tid, model, ver)
        summary_uri = self.a.build_uri(pid, vid, tid, model, ver, "keyframes.json")

        result = run_keyframe_extraction(
            video_path=video_path,
            shots_data={"shots": shots},
            fps_num=probe.fps_num,
            fps_den=probe.fps_den,
            frame_count=probe.frame_count,
            video_width=probe.width,
            video_height=probe.height,
            shots_artifact_id=shots_artifact_id,
            normalized_video_artifact_id=normalized_video_artifact_id,
            video_id=vid,
            keyframes_dir=keyframes_dir,
            keyframes_uri_prefix=summary_uri.rsplit("/", 1)[0],
        )
        if result.status != "SUCCEEDED":
            raise RuntimeError(f"Keyframe failed: {result.error_message}")

        with get_sync_session() as session:
            artifact = self.a.write_artifact(
                project_id=pid,
                video_id=vid,
                task_id=tid,
                model_name=model,
                model_version=ver,
                run_id=run_id,
                filename="keyframes.json",
                data=result.summary_data,
                artifact_type="shot_keyframes",
                output_role="keyframes",
                db_session=session,
            )
            model_run = session.get(ModelRun, run_id)
            if model_run:
                _mark_run_succeeded(model_run)
                session.commit()

        self._update_status(tid, "RUNNING", "extract_keyframes", 55)
        return artifact["artifact_id"]

    # ------------------------------------------------------------------
    # Step 4: Transcribe (Doubao ASR)
    # ------------------------------------------------------------------

    def _transcribe(
        self,
        pid: str,
        tid: str,
        vid: str,
        audio_artifact_id: str,
        *,
        use_cache: bool = True,
    ) -> str | None:
        if not audio_artifact_id:
            self._update_status(tid, "RUNNING", "transcribe", 78)
            return None  # non-fatal: video has no audio track

        from models.doubao_asr.adapter import DoubaoASRAdapter

        model, ver = "doubao_asr", "1.0.0"
        cache_key = canonical_cache_key(
            stage="audio.transcribe",
            model_name=model,
            model_version=ver,
            inputs={
                "video_id": vid,
                "audio": self.cache.artifact_fingerprint(audio_artifact_id),
            },
            parameters={"language": "zh-CN"},
            implementation="doubao-seedasr-contract-v2",
        )
        hit = (
            self.cache.find(
                video_id=vid,
                cache_key=cache_key,
                required_roles={"subtitles"},
            )
            if use_cache
            else None
        )
        if hit is None and use_cache:
            legacy = self._find_reusable_asr(vid, audio_artifact_id)
            if legacy is not None:
                source_artifact_id, source_run_id = legacy
                self.cache.promote_legacy_run(source_run_id, cache_key)
                hit = CacheHit(
                    source_run_id=source_run_id,
                    cache_key=cache_key,
                    outputs={"subtitles": self.cache.artifact(source_artifact_id)},
                )
        run_id = self._create_run(
            tid,
            vid,
            model,
            ver,
            cache_key=None if hit else cache_key,
            parameters={"language": "zh-CN"},
        )
        self._update_status(tid, "RUNNING", "transcribe", 72)
        artifact_id = audio_artifact_id

        # Query Artifact from DB to get real artifact_id
        from core.database.models import Artifact as ArtModel

        with get_sync_session() as s:
            art = s.get(ArtModel, artifact_id)
            if art is None:
                raise RuntimeError(f"Audio artifact {artifact_id} not found in DB")
            if art.artifact_type != "audio.normalized":
                raise RuntimeError(
                    f"Artifact {artifact_id} is {art.artifact_type}, expected audio.normalized"
                )
            real_artifact_id = art.artifact_id

        if hit:
            self._record_cache_hit(
                run_id=run_id,
                hit=hit,
                input_artifact_ids={"audio": real_artifact_id},
                complete=False,
            )
            with open(self.a.resolve(hit.outputs["subtitles"].uri), encoding="utf-8") as file:
                source_segments = json.load(file).get("subtitle_segments", [])
            segments = source_segments
        else:
            segments = None

        # Record ModelRun input
        from core.database.models import ModelRunInput

        if not hit:
            with get_sync_session() as s:
                s.add(
                    ModelRunInput(
                        run_id=run_id,
                        artifact_id=real_artifact_id,
                        input_role="audio",
                    )
                )
                s.commit()

        if not hit:
            # Generate signed provider URL using REAL artifact_id + project_id
            audio_url = self.a.storage.create_provider_url(
                real_artifact_id,
                project_id=pid,
                ttl_s=1800,
            )

            adapter = DoubaoASRAdapter()
            adapter.load()
            output = adapter.predict(
                {
                    "schema_version": "1.0",
                    "task_id": tid,
                    "video_id": vid,
                    "model": {"name": model, "version": ver},
                    "input": {"audio_url": audio_url},
                    "parameters": {"language": "zh-CN"},
                }
            )

        if not hit and output.get("status") != "SUCCEEDED":
            err = output.get("error", {})
            with get_sync_session() as s:
                mr = s.get(ModelRun, run_id)
                if mr:
                    mr.status = "FAILED"
                    mr.error_code = err.get("code", "TRANSCRIPTION_FAILED")
                    mr.error_message = err.get("message", "")
                    mr.finished_at = _now()
                    mr.retryable = err.get("retryable", False)
                    s.commit()
            raise RuntimeError(f"Transcription failed: {err}")

        if not hit:
            segments = output.get("artifacts", {}).get("subtitle_segments", [])
        canonical_segments = []
        for segment in segments:
            start_ms = max(0, int(segment.get("start_ms", 0)))
            canonical_segments.append(
                {
                    **segment,
                    "subtitle_id": _new_id(),
                    "video_id": vid,
                    "start_ms": start_ms,
                    "end_ms": max(start_ms, int(segment.get("end_ms", start_ms))),
                }
            )
        if not canonical_segments:
            raise RuntimeError("REQUIRED_EVIDENCE_MISSING: ASR returned no subtitle segments")

        from core.database.models import SubtitleSegment

        with get_sync_session() as s:
            artifact = self.a.write_artifact(
                project_id=pid,
                video_id=vid,
                task_id=tid,
                model_name=model,
                model_version=ver,
                run_id=run_id,
                filename="subtitles.json",
                data={"video_id": vid, "subtitle_segments": canonical_segments},
                artifact_type="subtitle_segments",
                output_role="subtitles",
                db_session=s,
            )
            for segment in canonical_segments:
                s.add(
                    SubtitleSegment(
                        subtitle_id=segment["subtitle_id"],
                        video_id=vid,
                        producer_run_id=run_id,
                        start_ms=segment["start_ms"],
                        end_ms=segment["end_ms"],
                        text=segment.get("text", ""),
                        language=segment.get("language"),
                        confidence=segment.get("confidence"),
                    )
                )
            mr = s.get(ModelRun, run_id)
            if mr:
                _mark_run_succeeded(mr)
            s.commit()

        self._update_status(tid, "RUNNING", "transcribe", 78)
        return artifact["artifact_id"]

    def _find_reusable_asr(
        self, video_id: str, current_audio_artifact_id: str
    ) -> tuple[str, str] | None:
        """Find a pre-cache ASR result whose audio bytes are identical."""
        expected_sha = self.cache.artifact_fingerprint(current_audio_artifact_id)
        with get_sync_session() as session:
            runs = list(
                session.execute(
                    select(ModelRun)
                    .where(
                        ModelRun.video_id == video_id,
                        ModelRun.model_name == "doubao_asr",
                        ModelRun.model_version == "1.0.0",
                        ModelRun.status == "SUCCEEDED",
                    )
                    .order_by(ModelRun.finished_at.desc())
                ).scalars()
            )
            for run in runs:
                audio = session.execute(
                    select(Artifact)
                    .join(ModelRunInput, ModelRunInput.artifact_id == Artifact.artifact_id)
                    .where(
                        ModelRunInput.run_id == run.run_id,
                        ModelRunInput.input_role == "audio",
                    )
                    .limit(1)
                ).scalar_one_or_none()
                output = session.execute(
                    select(Artifact)
                    .join(ModelRunOutput, ModelRunOutput.artifact_id == Artifact.artifact_id)
                    .where(
                        ModelRunOutput.run_id == run.run_id,
                        ModelRunOutput.output_role == "subtitles",
                    )
                    .limit(1)
                ).scalar_one_or_none()
                if audio and output and (audio.sha256 or f"uri:{audio.uri}") == expected_sha:
                    return output.artifact_id, run.run_id
        return None

    # ------------------------------------------------------------------
    # Step 5: hierarchical subtitle semantic continuity
    # ------------------------------------------------------------------

    def _score_subtitle_semantics(
        self,
        pid: str,
        tid: str,
        vid: str,
        *,
        subtitle_artifact_id: str,
        shots_artifact_id: str,
        use_cache: bool = True,
    ) -> str:
        from core.database.models import Artifact
        from models.subtitle_semantic.adapter import SubtitleSemanticAdapter

        model, ver = "subtitle_semantic", "1.1.0"
        subtitle_path = self.a.resolve(self._artifact_uri(subtitle_artifact_id))
        with open(subtitle_path, encoding="utf-8") as file:
            subtitle_data = json.load(file)
        with open(self.a.resolve(self._artifact_uri(shots_artifact_id)), encoding="utf-8") as file:
            shots_data = json.load(file)
        subtitles = subtitle_data.get("subtitle_segments", [])
        shots = shots_data.get("shots", [])
        from core.config import get_settings

        settings = get_settings()
        semantic_parameters = {
            "global_limit": settings.subtitle_semantic_global_limit,
            "local_limit": settings.subtitle_semantic_local_limit,
            "summary_chunk_chars": settings.subtitle_semantic_summary_chunk_chars,
            "summary_chunk_duration_ms": settings.subtitle_semantic_summary_chunk_duration_ms,
            "context_ms": settings.subtitle_semantic_context_ms,
            "rescore_batch_size": settings.subtitle_semantic_rescore_batch_size,
            "local_concurrency": settings.subtitle_semantic_local_concurrency,
            "local_min_chars": settings.subtitle_semantic_local_min_chars,
            "local_min_segments": settings.subtitle_semantic_local_min_segments,
            "max_snap_ms": settings.subtitle_semantic_max_snap_ms,
            "max_snap_shots": settings.subtitle_semantic_max_snap_shots,
            "llm_model": settings.subtitle_llm_model,
            "llm_base_url": settings.subtitle_llm_base_url,
        }
        cache_key = canonical_cache_key(
            stage="subtitle.semantic_continuity",
            model_name=model,
            model_version=ver,
            inputs={
                "video_id": vid,
                "subtitles": hash_json(_subtitle_content(subtitles)),
                "shot_timeline": hash_json(_shot_timeline(shots)),
            },
            parameters=semantic_parameters,
            implementation="hierarchical-subtitle-continuity-v3",
        )
        hit = (
            self.cache.find(
                video_id=vid,
                cache_key=cache_key,
                required_roles={"continuity"},
            )
            if use_cache
            else None
        )
        cached_data = None
        run_id = self._create_run(
            tid,
            vid,
            model,
            ver,
            cache_key=None if hit else cache_key,
            parameters=semantic_parameters,
        )
        self._update_status(tid, "RUNNING", "score_subtitle_semantics", 80)
        with get_sync_session() as session:
            if session.get(Artifact, subtitle_artifact_id) is None:
                raise RuntimeError(f"Subtitle Artifact {subtitle_artifact_id} is missing")
            if session.get(Artifact, shots_artifact_id) is None:
                raise RuntimeError(f"Shots Artifact {shots_artifact_id} is missing")
            if not hit:
                session.add_all(
                    [
                        ModelRunInput(
                            run_id=run_id,
                            artifact_id=subtitle_artifact_id,
                            input_role="subtitles",
                        ),
                        ModelRunInput(
                            run_id=run_id,
                            artifact_id=shots_artifact_id,
                            input_role="shots",
                        ),
                    ]
                )
            session.commit()

        if hit is not None:
            self._record_cache_hit(
                run_id=run_id,
                hit=hit,
                input_artifact_ids={
                    "subtitles": subtitle_artifact_id,
                    "shots": shots_artifact_id,
                },
                complete=False,
            )
            if cached_data is None:
                with open(self.a.resolve(hit.outputs["continuity"].uri), encoding="utf-8") as file:
                    cached_data = json.load(file)
                cached_data = _remap_cached_subtitle_continuity(shots, shots, cached_data)
            if cached_data is None:
                raise RuntimeError("CACHE_CORRUPT: subtitle continuity cannot be remapped")
            with get_sync_session() as session:
                artifact = self.a.write_artifact(
                    project_id=pid,
                    video_id=vid,
                    task_id=tid,
                    model_name=model,
                    model_version=ver,
                    run_id=run_id,
                    filename="subtitle_continuity.json",
                    data=cached_data,
                    artifact_type="subtitle_continuity",
                    output_role="continuity",
                    db_session=session,
                )
                model_run = session.get(ModelRun, run_id)
                if model_run:
                    _mark_run_succeeded(model_run)
                session.commit()
            self._update_status(tid, "RUNNING", "score_subtitle_semantics", 90)
            return artifact["artifact_id"]

        from apps.api.services.subtitle_stage_cache import SubtitleStageCache

        stage_cache = SubtitleStageCache(
            project_id=pid,
            video_id=vid,
            task_id=tid,
            input_artifact_ids={
                "subtitles": subtitle_artifact_id,
                "shots": shots_artifact_id,
            },
            model_identity={
                "model": settings.subtitle_llm_model,
                "base_url": settings.subtitle_llm_base_url,
                "prompt_contract": "subtitle-semantic-v3",
            },
            artifacts=self.a,
            cache=self.cache,
        )
        adapter = SubtitleSemanticAdapter(stage_cache=stage_cache)
        output = adapter.predict(
            {
                "schema_version": "1.0",
                "task_id": tid,
                "video_id": vid,
                "run_id": run_id,
                "model": {"name": model, "version": ver},
                "input": {
                    "subtitle_segments": subtitle_data.get("subtitle_segments", []),
                    "shots": shots_data.get("shots", []),
                },
                "parameters": semantic_parameters,
            }
        )
        if output.get("status") != "SUCCEEDED":
            error = output.get("error", {})
            with get_sync_session() as session:
                model_run = session.get(ModelRun, run_id)
                if model_run:
                    model_run.status = "FAILED"
                    model_run.error_code = error.get("code")
                    model_run.error_message = error.get("message")
                    model_run.retryable = error.get("retryable", True)
                    model_run.finished_at = _now()
                    session.commit()
            raise RuntimeError(f"Subtitle semantic analysis failed: {error}")

        with get_sync_session() as session:
            artifact = self.a.write_artifact(
                project_id=pid,
                video_id=vid,
                task_id=tid,
                model_name=model,
                model_version=ver,
                run_id=run_id,
                filename="subtitle_continuity.json",
                data=adapter._last_result,
                artifact_type="subtitle_continuity",
                output_role="continuity",
                db_session=session,
            )
            model_run = session.get(ModelRun, run_id)
            if model_run:
                _mark_run_succeeded(model_run)
            session.commit()
        self._update_status(tid, "RUNNING", "score_subtitle_semantics", 90)
        return artifact["artifact_id"]

    def _find_reusable_subtitle_continuity(
        self,
        video_id: str,
        current_shots: list[dict],
        current_subtitles: list[dict],
    ) -> tuple[dict, str, str] | None:
        """Compatibility bridge for successful pre-cache semantic runs."""
        with get_sync_session() as session:
            runs = list(
                session.execute(
                    select(ModelRun)
                    .where(
                        ModelRun.video_id == video_id,
                        ModelRun.model_name == "subtitle_semantic",
                        ModelRun.model_version == "1.0.0",
                        ModelRun.status == "SUCCEEDED",
                    )
                    .order_by(ModelRun.finished_at.desc())
                ).scalars()
            )
            candidates: list[tuple[str, str, str, str, str]] = []
            for run in runs:
                shots_artifact = session.execute(
                    select(Artifact)
                    .join(ModelRunInput, ModelRunInput.artifact_id == Artifact.artifact_id)
                    .where(
                        ModelRunInput.run_id == run.run_id,
                        ModelRunInput.input_role == "shots",
                    )
                    .limit(1)
                ).scalar_one_or_none()
                output_artifact = session.execute(
                    select(Artifact)
                    .join(ModelRunOutput, ModelRunOutput.artifact_id == Artifact.artifact_id)
                    .where(
                        ModelRunOutput.run_id == run.run_id,
                        ModelRunOutput.output_role == "continuity",
                    )
                    .limit(1)
                ).scalar_one_or_none()
                subtitle_artifact = session.execute(
                    select(Artifact)
                    .join(ModelRunInput, ModelRunInput.artifact_id == Artifact.artifact_id)
                    .where(
                        ModelRunInput.run_id == run.run_id,
                        ModelRunInput.input_role == "subtitles",
                    )
                    .limit(1)
                ).scalar_one_or_none()
                if shots_artifact and subtitle_artifact and output_artifact:
                    candidates.append(
                        (
                            shots_artifact.uri,
                            subtitle_artifact.uri,
                            output_artifact.uri,
                            output_artifact.artifact_id,
                            run.run_id,
                        )
                    )

        current_transcript = _subtitle_content(current_subtitles)
        for shots_uri, subtitle_uri, output_uri, output_artifact_id, source_run_id in candidates:
            try:
                with open(self.a.resolve(shots_uri), encoding="utf-8") as file:
                    cached_shots = json.load(file).get("shots", [])
                with open(self.a.resolve(subtitle_uri), encoding="utf-8") as file:
                    cached_subtitles = json.load(file).get("subtitle_segments", [])
                with open(self.a.resolve(output_uri), encoding="utf-8") as file:
                    cached_data = json.load(file)
            except (OSError, ValueError, TypeError):
                continue
            if _subtitle_content(cached_subtitles) != current_transcript:
                continue
            remapped = _remap_cached_subtitle_continuity(
                current_shots,
                cached_shots,
                cached_data,
            )
            if remapped is not None:
                return remapped, output_artifact_id, source_run_id
        return None

    # ------------------------------------------------------------------
    # Step 6: VLM scoring
    # ------------------------------------------------------------------

    def _score_vlm(
        self,
        pid: str,
        tid: str,
        vid: str,
        shots: list[dict],
        *,
        shots_artifact_id: str,
        keyframes_artifact_id: str,
        use_cache: bool = True,
    ) -> str | None:
        from models.doubao_vision.adapter import DoubaoVisionAdapter
        from models.vlm_boundary.prompts import (
            SHOT_DESCRIPTOR_SYSTEM,
            SHOT_DESCRIPTOR_TEMPLATE,
        )

        if len(shots) < 2:
            return None

        model, ver = "doubao_vision", "1.2.0"
        vision_parameters = {
            "descriptor_mode": "dynamic_frame_batched_registry",
            "max_attempts": 2,
            "concurrency": 3,
            "max_tokens": 900,
        }
        keyframe_fingerprint = self._keyframe_content_fingerprint(keyframes_artifact_id)
        cache_key = canonical_cache_key(
            stage="scene.score_visual_continuity",
            model_name=model,
            model_version=ver,
            inputs={
                "video_id": vid,
                "shot_timeline": hash_json(_shot_timeline(shots)),
                "keyframes": keyframe_fingerprint,
            },
            parameters={
                **vision_parameters,
                "prompt": hash_json([SHOT_DESCRIPTOR_SYSTEM, SHOT_DESCRIPTOR_TEMPLATE]),
            },
            implementation="doubao-vision-batched-registry-contract-v2",
        )
        hit = (
            self.cache.find(
                video_id=vid,
                cache_key=cache_key,
                required_roles={"scores"},
            )
            if use_cache
            else None
        )
        run_id = self._create_run(
            tid,
            vid,
            model,
            ver,
            cache_key=None if hit else cache_key,
            parameters=vision_parameters,
        )
        if hit:
            self._record_cache_hit(
                run_id=run_id,
                hit=hit,
                input_artifact_ids={
                    "shots": shots_artifact_id,
                    "keyframes": keyframes_artifact_id,
                },
                complete=False,
            )
            with open(self.a.resolve(hit.outputs["scores"].uri), encoding="utf-8") as file:
                vision_result = json.load(file)
            source_scores = vision_result.get("scores", [])
            if len(source_scores) != len(shots) - 1:
                raise RuntimeError("CACHE_CORRUPT: Vision score count does not match shots")
            scores = [
                {**score, "shot_id": str(shots[index]["shot_id"])}
                for index, score in enumerate(source_scores)
            ]
            source_descriptors = vision_result.get("shot_descriptors", [])
            if source_descriptors and len(source_descriptors) != len(shots):
                raise RuntimeError("CACHE_CORRUPT: Vision descriptor count does not match shots")
            vision_result = {
                **vision_result,
                "video_id": vid,
                "scores": scores,
                "shot_descriptors": [
                    {**descriptor, "shot_id": str(shots[index]["shot_id"])}
                    for index, descriptor in enumerate(source_descriptors)
                ],
            }
        else:
            scores = None
            vision_result = None
        with get_sync_session() as session:
            if not hit:
                session.add_all(
                    [
                        ModelRunInput(
                            run_id=run_id,
                            artifact_id=shots_artifact_id,
                            input_role="shots",
                        ),
                        ModelRunInput(
                            run_id=run_id,
                            artifact_id=keyframes_artifact_id,
                            input_role="keyframes",
                        ),
                    ]
                )
            session.commit()

        if hit is not None:
            with get_sync_session() as session:
                artifact = self.a.write_artifact(
                    project_id=pid,
                    video_id=vid,
                    task_id=tid,
                    model_name=model,
                    model_version=ver,
                    run_id=run_id,
                    filename="doubao_vision_scores.json",
                    data=vision_result,
                    artifact_type="location_character_scores",
                    output_role="scores",
                    db_session=session,
                )
                model_run = session.get(ModelRun, run_id)
                if model_run:
                    _mark_run_succeeded(model_run)
                session.commit()
            self._update_status(tid, "RUNNING", "score_vlm", 70)
            return artifact["artifact_id"]

        shots_uri = self._artifact_uri(shots_artifact_id)
        keyframes_uri = self._artifact_uri(keyframes_artifact_id)

        resume_state = self._load_vision_checkpoint(vid, cache_key)

        def save_checkpoint(state: dict) -> None:
            completed = len(state.get("shot_descriptors") or [])
            checkpoint = {"cache_key": cache_key, **state}
            self.a.write_artifact(
                project_id=pid,
                video_id=vid,
                task_id=tid,
                model_name=model,
                model_version=ver,
                run_id=run_id,
                filename=f"vision_checkpoint_{completed:05d}.json",
                data=checkpoint,
                artifact_type="vision_descriptor_checkpoint",
                output_role=f"checkpoint_{completed:05d}",
            )

        adapter = DoubaoVisionAdapter(
            resume_state=resume_state,
            checkpoint_callback=save_checkpoint,
        )
        adapter.load()
        self._update_status(tid, "RUNNING", "score_vlm", 60)
        output = adapter.predict(
            {
                "schema_version": "1.0",
                "task_id": tid,
                "video_id": vid,
                "run_id": run_id,
                "model": {"name": model, "version": ver},
                "input": {"shots_uri": shots_uri, "keyframes_uri": keyframes_uri},
                "parameters": vision_parameters,
            }
        )

        if output.get("status") != "SUCCEEDED":
            raise WorkflowStepError(output.get("error", {}))

        vision_result = adapter._last_result
        scores = vision_result.get("scores", [])
        expected_ids = [str(shot["shot_id"]) for shot in shots[:-1]]
        returned_ids = [str(item.get("shot_id", "")) for item in scores]
        if len(scores) != len(expected_ids) or set(returned_ids) != set(expected_ids):
            raise RuntimeError(
                "VISION_OUTPUT_INCOMPLETE: expected exactly one score for every shot boundary"
            )
        if len(returned_ids) != len(set(returned_ids)):
            raise RuntimeError("VISION_OUTPUT_INVALID: duplicate shot_id values")
        for item in scores:
            for field in ("location_change", "character_group_change"):
                try:
                    value = float(item[field])
                except (KeyError, TypeError, ValueError) as exc:
                    raise RuntimeError(
                        f"VISION_OUTPUT_INVALID: {field} is missing or non-numeric"
                    ) from exc
                if not 0.0 <= value <= 100.0:
                    raise RuntimeError(f"VISION_OUTPUT_INVALID: {field} must be within [0, 100]")
        with get_sync_session() as session:
            artifact = self.a.write_artifact(
                project_id=pid,
                video_id=vid,
                task_id=tid,
                model_name=model,
                model_version=ver,
                run_id=run_id,
                filename="doubao_vision_scores.json",
                data=vision_result,
                artifact_type="location_character_scores",
                output_role="scores",
                db_session=session,
            )
            model_run = session.get(ModelRun, run_id)
            if model_run:
                _mark_run_succeeded(model_run)
            session.commit()
        self._update_status(tid, "RUNNING", "score_vlm", 70)
        return artifact["artifact_id"]

    def _load_vision_checkpoint(self, video_id: str, cache_key: str) -> dict:
        """Return the newest compatible cumulative descriptor checkpoint."""
        with get_sync_session() as session:
            candidates = list(
                session.execute(
                    select(Artifact)
                    .where(
                        Artifact.video_id == video_id,
                        Artifact.artifact_type == "vision_descriptor_checkpoint",
                    )
                    .order_by(Artifact.created_at.desc())
                    .limit(200)
                ).scalars()
            )
        best: dict = {}
        for artifact in candidates:
            try:
                with open(self.a.resolve(artifact.uri), encoding="utf-8") as file:
                    state = json.load(file)
            except (OSError, ValueError, json.JSONDecodeError):
                continue
            if state.get("cache_key") != cache_key:
                continue
            if len(state.get("shot_descriptors") or []) > len(
                best.get("shot_descriptors") or []
            ):
                best = state
        return best

    def _find_reusable_vision_scores(
        self,
        video_id: str,
        current_shots: list[dict],
        current_keyframe_fingerprint: str,
    ) -> tuple[list[dict], str, str] | None:
        """Compatibility bridge for successful pre-cache Vision runs."""
        with get_sync_session() as session:
            runs = list(
                session.execute(
                    select(ModelRun)
                    .where(
                        ModelRun.video_id == video_id,
                        ModelRun.model_name == "doubao_vision",
                        ModelRun.model_version == "1.0.0",
                        ModelRun.status == "SUCCEEDED",
                    )
                    .order_by(ModelRun.finished_at.desc())
                ).scalars()
            )
            candidates: list[tuple[str, str, str, str]] = []
            for run in runs:
                shots_artifact = session.execute(
                    select(Artifact)
                    .join(ModelRunInput, ModelRunInput.artifact_id == Artifact.artifact_id)
                    .where(
                        ModelRunInput.run_id == run.run_id,
                        ModelRunInput.input_role == "shots",
                    )
                    .limit(1)
                ).scalar_one_or_none()
                score_artifact = session.execute(
                    select(Artifact)
                    .join(ModelRunOutput, ModelRunOutput.artifact_id == Artifact.artifact_id)
                    .where(
                        ModelRunOutput.run_id == run.run_id,
                        ModelRunOutput.output_role == "scores",
                    )
                    .limit(1)
                ).scalar_one_or_none()
                keyframe_artifact = session.execute(
                    select(Artifact)
                    .join(ModelRunInput, ModelRunInput.artifact_id == Artifact.artifact_id)
                    .where(
                        ModelRunInput.run_id == run.run_id,
                        ModelRunInput.input_role == "keyframes",
                    )
                    .limit(1)
                ).scalar_one_or_none()
                if shots_artifact and keyframe_artifact and score_artifact:
                    candidates.append(
                        (
                            shots_artifact.uri,
                            keyframe_artifact.artifact_id,
                            score_artifact.artifact_id,
                            run.run_id,
                        )
                    )

        for shots_uri, keyframe_artifact_id, score_artifact_id, source_run_id in candidates:
            try:
                candidate_keyframes = self._keyframe_content_fingerprint(keyframe_artifact_id)
            except (OSError, ValueError, TypeError, KeyError):
                continue
            if candidate_keyframes != current_keyframe_fingerprint:
                continue
            with get_sync_session() as session:
                score_artifact = session.get(Artifact, score_artifact_id)
                score_uri = score_artifact.uri if score_artifact else None
            if not score_uri:
                continue
            try:
                with open(self.a.resolve(shots_uri), encoding="utf-8") as file:
                    cached_shots = json.load(file).get("shots", [])
                with open(self.a.resolve(score_uri), encoding="utf-8") as file:
                    cached_scores = json.load(file).get("scores", [])
            except (OSError, ValueError, TypeError):
                continue
            remapped = _remap_cached_vision_scores(
                current_shots,
                cached_shots,
                cached_scores,
            )
            if remapped is not None:
                return remapped, score_artifact_id, source_run_id
        return None

    # ------------------------------------------------------------------
    # Step 6: Merge scores → final scenes
    # ------------------------------------------------------------------

    def _merge_scores(
        self,
        pid: str,
        tid: str,
        vid: str,
        mode: str,
        lw: int,
        cw: int,
        sw: int,
        min_s: int,
        intensity: str,
        input_artifacts: dict[str, str | None],
    ):
        model, ver = "merge", "1.0.0"
        run_id = self._create_run(tid, vid, model, ver)

        shots_data = self.a.read_json(pid, vid, tid, "ffmpeg_scene", "1.0.0", "ffmpeg_scene.json")
        shots = shots_data["shots"]

        vlm_scores = []
        vision_artifact_id = input_artifacts.get("visual_continuity")
        if vision_artifact_id:
            with open(
                self.a.resolve(self._artifact_uri(vision_artifact_id)), encoding="utf-8"
            ) as file:
                vlm_scores = json.load(file).get("scores", [])

        subtitle_scores = []
        subtitle_artifact_id = input_artifacts.get("subtitle_continuity")
        if subtitle_artifact_id:
            with open(
                self.a.resolve(self._artifact_uri(subtitle_artifact_id)), encoding="utf-8"
            ) as file:
                subtitle_scores = json.load(file).get("boundaries", [])

        weights = _score_weights(mode, lw, cw, sw)

        vlm_by_shot = {}
        for s in vlm_scores:
            vlm_by_shot[s.get("shot_id", "")] = {
                "location": s.get("location_change", 0),
                "character": s.get("character_group_change", 0),
            }
        subtitle_by_shot = {item.get("shot_id", ""): item for item in subtitle_scores}

        boundaries = []
        for boundary_index, shot in enumerate(shots[:-1]):
            v = vlm_by_shot.get(shot["shot_id"])
            location_change = min(100.0, max(0.0, float(v["location"]))) if v is not None else None
            character_change = (
                min(100.0, max(0.0, float(v["character"]))) if v is not None else None
            )
            subtitle_item = subtitle_by_shot.get(shot["shot_id"])
            has_subtitle_artifact = bool(input_artifacts.get("subtitle_continuity"))
            subtitle_continuity = (
                min(1.0, max(0.0, float(subtitle_item["subtitle_continuity"])))
                if subtitle_item is not None
                else (1.0 if has_subtitle_artifact else None)
            )
            score = round(
                _weighted_change(
                    {
                        "location": location_change / 100.0
                        if location_change is not None
                        else None,
                        "character": (
                            character_change / 100.0 if character_change is not None else None
                        ),
                        "subtitle": (
                            1.0 - subtitle_continuity if subtitle_continuity is not None else None
                        ),
                    },
                    weights,
                ),
                4,
            )
            boundaries.append(
                {
                    "shot_id": shot["shot_id"],
                    "boundary_index": boundary_index,
                    "timestamp_ms": shot["end_ms"],
                    "scene_score": score,
                    "location_change": location_change,
                    "character_group_change": character_change,
                    "subtitle_continuity": subtitle_continuity,
                }
            )

        min_ms = min_s * 1000
        ratio = _INTENSITY_RATIOS.get(intensity, _INTENSITY_RATIOS["medium"])
        target_count = min(len(boundaries), max(3, int(len(shots) * ratio)))
        selected = _select_boundaries(
            boundaries,
            min_distance_ms=min_ms,
            target_count=target_count,
        )

        scenes, scene_evidence = assemble_scenes(
            video_id=vid,
            shots=shots,
            selected_boundaries=selected,
        )
        selected_by_index = {
            boundary["boundary_index"]: {
                "selection_rank": rank,
                "scene_id": scenes[rank]["scene_id"],
            }
            for rank, boundary in enumerate(selected)
        }
        result_data = {
            "schema_version": "1.0",
            "video_id": vid,
            "scenes": scenes,
            "scene_evidence": scene_evidence,
            "boundaries": boundaries,
            "candidate_boundaries": selected,
            "selection": {
                "weights": weights,
                "intensity": intensity,
                "target_count": target_count,
                "selected_count": len(selected),
                "min_distance_ms": min_ms,
            },
        }

        # Artifact, ModelRunOutput, Scene, Evidence, and ModelRun status share
        # one database transaction. The diagnostic file may remain if the DB
        # transaction fails, but the task cannot be marked successful.
        with get_sync_session() as session:
            for role, artifact_id in input_artifacts.items():
                if artifact_id:
                    session.add(
                        ModelRunInput(
                            run_id=run_id,
                            artifact_id=artifact_id,
                            input_role=role,
                        )
                    )
            self.a.write_artifact(
                project_id=pid,
                video_id=vid,
                task_id=tid,
                model_name=model,
                model_version=ver,
                run_id=run_id,
                filename=f"{mode}_final.json",
                data=result_data,
                artifact_type="final_scenes",
                output_role="final",
                db_session=session,
            )
            for scene in scenes:
                session.add(
                    Scene(
                        scene_id=scene["scene_id"],
                        video_id=vid,
                        producer_run_id=run_id,
                        index=scene["index"],
                        start_ms=scene["start_ms"],
                        end_ms=scene["end_ms"],
                        shot_ids=scene["shot_ids"],
                        boundary_confidence=scene["boundary_confidence"],
                        scene_score=scene["scene_score"],
                    )
                )
            # CandidateBoundary and SceneEvidence refer to Scene IDs. Flush the
            # parent rows first because these ORM models do not share relationships
            # that SQLAlchemy can use to infer dependency order automatically.
            session.flush()
            for item in scene_evidence:
                session.add(
                    SceneEvidence(
                        evidence_id=_new_id(),
                        scene_id=item["scene_id"],
                        visual_continuity=item["visual_continuity"],
                        character_continuity=item["character_continuity"],
                        location_continuity=item["location_continuity"],
                        subtitle_continuity=item["subtitle_continuity"],
                        audio_continuity=item["audio_continuity"],
                        temporal_gap_ms=item["temporal_gap_ms"],
                    )
                )
            for boundary in boundaries:
                selected_info = selected_by_index.get(boundary["boundary_index"])
                location_change = boundary["location_change"]
                character_change = boundary["character_group_change"]
                candidate = CandidateBoundarySchema(
                    candidate_id=_new_id(),
                    video_id=vid,
                    producer_run_id=run_id,
                    shot_id=boundary["shot_id"],
                    scene_id=selected_info["scene_id"] if selected_info else None,
                    boundary_index=boundary["boundary_index"],
                    timestamp_ms=boundary["timestamp_ms"],
                    scene_score=boundary["scene_score"],
                    location_continuity=(
                        round(1.0 - location_change / 100.0, 4)
                        if location_change is not None
                        else None
                    ),
                    character_continuity=(
                        round(1.0 - character_change / 100.0, 4)
                        if character_change is not None
                        else None
                    ),
                    subtitle_continuity=boundary["subtitle_continuity"],
                    selected=selected_info is not None,
                    selection_rank=(selected_info["selection_rank"] if selected_info else None),
                )
                session.add(CandidateBoundary(**candidate.model_dump()))
            model_run = session.get(ModelRun, run_id)
            if model_run is None:
                raise RuntimeError(f"Merge ModelRun {run_id} not found")
            model_run.parameters_json = {
                "score_mode": mode,
                "requested_weights": {
                    "location": lw,
                    "character": cw,
                    "subtitle": sw,
                },
                "normalized_weights": weights,
                "cut_intensity": intensity,
                "target_count": target_count,
                "selected_count": len(selected),
                "min_distance_ms": min_ms,
            }
            _mark_run_succeeded(model_run)
            session.commit()
        self._update_status(tid, "RUNNING", "merge_scores", 95)

    # ------------------------------------------------------------------
    # DB helpers
    # ------------------------------------------------------------------

    def _record_cache_hit(
        self,
        *,
        run_id: str,
        hit: CacheHit,
        input_artifact_ids: dict[str, str] | None = None,
        link_cached_outputs: bool = False,
        complete: bool = True,
    ) -> None:
        """Record cache provenance without assigning the origin cache key twice."""
        with get_sync_session() as session:
            for role, artifact_id in (input_artifact_ids or {}).items():
                session.add(
                    ModelRunInput(
                        run_id=run_id,
                        artifact_id=artifact_id,
                        input_role=role,
                    )
                )
            for role, artifact in hit.outputs.items():
                session.add(
                    ModelRunInput(
                        run_id=run_id,
                        artifact_id=artifact.artifact_id,
                        input_role=f"cache_source:{role}",
                    )
                )
                if link_cached_outputs:
                    session.add(
                        ModelRunOutput(
                            run_id=run_id,
                            artifact_id=artifact.artifact_id,
                            output_role=role,
                        )
                    )
            model_run = session.get(ModelRun, run_id)
            if model_run is None:
                raise RuntimeError(f"Cache-hit ModelRun {run_id} not found")
            model_run.parameters_json = self.cache.cache_metadata(hit)
            if complete:
                _mark_run_succeeded(model_run)
            session.commit()

    def _artifact_uri(self, artifact_id: str) -> str:
        return self.cache.artifact(artifact_id).uri

    def _keyframe_content_fingerprint(self, artifact_id: str) -> str:
        """Hash sampled image bytes and positions without task-scoped IDs/URIs."""
        with open(self.a.resolve(self._artifact_uri(artifact_id)), encoding="utf-8") as file:
            data = json.load(file)
        content = []
        for item in data.get("shots", []):
            content.append(
                [
                    {
                        "position_num": sample.get("position_num"),
                        "position_den": sample.get("position_den"),
                        "sha256": hash_file(self.a.resolve(sample["uri"])),
                    }
                    for sample in item.get("samples", [])
                ]
            )
        return hash_json(content)

    def _update_status(self, task_id: str, status: str, stage: str, progress: int):
        with get_sync_session() as session:
            repo = TaskRepository(session)
            repo.update_status(task_id, status)
            repo.update_progress(task_id, progress, stage=stage)
            session.commit()

    def _set_error(self, task_id: str, code: str, message: str):
        with get_sync_session() as session:
            TaskRepository(session).set_error(task_id, code, message)
            session.commit()

    def _fail_running_model_runs(self, task_id: str, error: Exception) -> None:
        """Close every unfinished step when the enclosing Workflow fails."""
        with get_sync_session() as session:
            running = (
                session.query(ModelRun)
                .filter(ModelRun.task_id == task_id, ModelRun.status == "RUNNING")
                .all()
            )
            for model_run in running:
                model_run.status = "FAILED"
                model_run.error_code = "STEP_FAILED"
                model_run.error_message = str(error)
                model_run.retryable = bool(getattr(error, "retryable", False))
                model_run.finished_at = _now()
            if running:
                session.commit()
