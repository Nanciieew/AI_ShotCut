"""TaskService — create/query tasks. Reuses existing video_id per §3.2."""

import uuid

from sqlalchemy import select

from core.database.models import (
    Artifact,
    CandidateBoundary,
    ModelRun,
    Scene,
    SceneEvidence,
    Shot,
    SubtitleSegment,
    Task,
    Video,
)
from core.database.repositories import TaskRepository
from core.database.session_sync import get_sync_session
from schemas.result import FinalResult


def _new_id() -> str:
    return uuid.uuid4().hex  # 32-char


class TaskService:
    """Task lifecycle management.

    create_task(project_id, video_id, parameters) — receives an existing
    video_id from the upload step. Does NOT copy source files or create
    a new Video record (§6.1).
    """

    def create_task(
        self,
        *,
        project_id: str,
        video_id: str,
        parameters: dict | None = None,
        retry_of_task_id: str | None = None,
        retry_count: int = 0,
    ) -> dict:
        tid = _new_id()

        with get_sync_session() as session:
            task_repo = TaskRepository(session)
            task_repo.create(
                task_id=tid,
                project_id=project_id,
                video_id=video_id,
                task_type="full_video_analysis",
                parameters_json=parameters,
                retry_of_task_id=retry_of_task_id,
                retry_count=retry_count,
            )
            session.commit()

        return {
            "task_id": tid,
            "video_id": video_id,
            "project_id": project_id,
            "status": "PENDING",
            "stage": "created",
            "progress": 0,
        }

    # ---- queries -----------------------------------------------------------

    async def get_task_status(self, task_id: str, db) -> dict:
        result = await db.execute(select(Task).where(Task.task_id == task_id))
        task = result.scalar_one_or_none()
        if task is None:
            return {"task_id": task_id, "status": "NOT_FOUND"}
        return {
            "task_id": task.task_id,
            "video_id": task.video_id,
            "project_id": task.project_id,
            "status": task.status,
            "stage": task.stage,
            "progress": task.progress,
            "error_code": task.error_code,
            "error_message": task.error_message,
        }

    async def get_video_results(self, video_id: str, db) -> dict:
        r = await db.execute(select(Video).where(Video.video_id == video_id))
        video = r.scalar_one_or_none()
        if video is None:
            return {"video_id": video_id, "status": "NOT_FOUND"}

        r = await db.execute(
            select(Task)
            .where(Task.video_id == video_id, Task.status == "SUCCEEDED")
            .order_by(Task.created_at.desc())
            .limit(1)
        )
        task = r.scalar_one_or_none()
        if task is None:
            return {
                "video_id": video_id,
                "status": "PENDING",
                "message": "No successful analysis task found",
            }

        r = await db.execute(
            select(ModelRun)
            .where(
                ModelRun.task_id == task.task_id,
                ModelRun.model_name == "ffmpeg_scene",
                ModelRun.status == "SUCCEEDED",
            )
            .order_by(ModelRun.started_at.desc())
            .limit(1)
        )
        shot_run = r.scalar_one_or_none()
        shots = []
        if shot_run is not None:
            r = await db.execute(
                select(Shot).where(Shot.producer_run_id == shot_run.run_id).order_by(Shot.index)
            )
            shots = list(r.scalars().all())

        video_data = {
            "video_id": video.video_id,
            "project_id": video.project_id,
            "source_uri": video.source_uri or "",
            "normalized_uri": video.normalized_uri or "",
            "audio_uri": video.audio_uri or "",
            "duration_ms": video.duration_ms or 0,
            "fps_num": video.fps_num or 24,
            "fps_den": video.fps_den or 1,
            "width": video.width or 1,
            "height": video.height or 1,
            "audio_sample_rate": video.audio_sample_rate or 16000,
        }
        shot_items = [
            {
                "shot_id": shot.shot_id,
                "video_id": shot.video_id,
                "index": shot.index,
                "start_ms": shot.start_ms,
                "end_ms": shot.end_ms,
                "start_frame": shot.start_frame,
                "end_frame_exclusive": shot.end_frame_exclusive,
                "boundary_type": shot.boundary_type,
                "confidence": shot.confidence,
            }
            for shot in shots
        ]

        scene_analysis = bool((task.parameters_json or {}).get("scene_analysis", True))
        if not scene_analysis:
            if shot_run is None:
                return {
                    "video_id": video_id,
                    "task_id": task.task_id,
                    "status": "INCOMPLETE",
                    "message": "Successful shot-only task has no successful shot ModelRun",
                }
            return FinalResult.model_validate(
                {
                    "result_type": "shot_detection",
                    "task_id": task.task_id,
                    "status": task.status,
                    "video": video_data,
                    "shots": shot_items,
                }
            ).model_dump()

        r = await db.execute(
            select(ModelRun)
            .where(
                ModelRun.task_id == task.task_id,
                ModelRun.model_name == "merge",
                ModelRun.status == "SUCCEEDED",
            )
            .order_by(ModelRun.started_at.desc())
            .limit(1)
        )
        merge_run = r.scalar_one_or_none()
        if merge_run is None:
            return {
                "video_id": video_id,
                "task_id": task.task_id,
                "status": "INCOMPLETE",
                "message": "Successful scene task has no successful merge ModelRun",
            }

        r = await db.execute(
            select(ModelRun)
            .where(
                ModelRun.task_id == task.task_id,
                ModelRun.model_name == "doubao_asr",
                ModelRun.status == "SUCCEEDED",
            )
            .order_by(ModelRun.started_at.desc())
            .limit(1)
        )
        asr_run = r.scalar_one_or_none()
        subtitles = []
        if asr_run is not None:
            r = await db.execute(
                select(SubtitleSegment)
                .where(SubtitleSegment.producer_run_id == asr_run.run_id)
                .order_by(SubtitleSegment.start_ms)
            )
            subtitles = list(r.scalars().all())

        r = await db.execute(
            select(Scene).where(Scene.producer_run_id == merge_run.run_id).order_by(Scene.index)
        )
        scenes = r.scalars().all()
        scene_ids = [scene.scene_id for scene in scenes]
        evidence_by_scene: dict[str, SceneEvidence] = {}
        if scene_ids:
            r = await db.execute(select(SceneEvidence).where(SceneEvidence.scene_id.in_(scene_ids)))
            evidence_by_scene = {item.scene_id: item for item in r.scalars().all()}

        r = await db.execute(
            select(Artifact)
            .join(ModelRun, Artifact.producer_run_id == ModelRun.run_id)
            .where(ModelRun.task_id == task.task_id)
            .order_by(Artifact.created_at)
        )
        artifacts = r.scalars().all()
        final_artifact = next(
            (item for item in reversed(artifacts) if item.artifact_type == "final_scenes"),
            None,
        )

        scene_items = [
            {
                "scene_id": scene.scene_id,
                "video_id": scene.video_id,
                "index": scene.index,
                "start_ms": scene.start_ms,
                "end_ms": scene.end_ms,
                "shot_ids": scene.shot_ids or [],
                "boundary_confidence": scene.boundary_confidence,
                "scene_score": scene.scene_score,
            }
            for scene in scenes
        ]
        evidence_items = [
            {
                "scene_id": item.scene_id,
                "visual_continuity": item.visual_continuity,
                "character_continuity": item.character_continuity,
                "location_continuity": item.location_continuity,
                "subtitle_continuity": item.subtitle_continuity,
                "audio_continuity": item.audio_continuity,
                "temporal_gap_ms": item.temporal_gap_ms,
            }
            for scene in scenes
            if (item := evidence_by_scene.get(scene.scene_id)) is not None
        ]
        r = await db.execute(
            select(CandidateBoundary)
            .where(
                CandidateBoundary.producer_run_id == merge_run.run_id,
                CandidateBoundary.selected.is_(True),
                CandidateBoundary.scene_id.is_not(None),
            )
            .order_by(CandidateBoundary.boundary_index)
        )
        selected_boundaries = list(r.scalars().all())
        candidate_boundaries = [
            {
                "scene_id": boundary.scene_id,
                "shot_id": boundary.shot_id,
                "boundary_index": boundary.boundary_index,
                "timestamp_ms": boundary.timestamp_ms,
                "scene_score": boundary.scene_score,
                "location_continuity": boundary.location_continuity,
                "character_continuity": boundary.character_continuity,
                "subtitle_continuity": boundary.subtitle_continuity,
            }
            for boundary in selected_boundaries
        ]

        return FinalResult.model_validate(
            {
                "result_type": "scene_analysis",
                "task_id": task.task_id,
                "status": task.status,
                "video": video_data,
                "shots": shot_items,
                "subtitles": [
                    {
                        "subtitle_id": subtitle.subtitle_id,
                        "video_id": subtitle.video_id,
                        "start_ms": subtitle.start_ms,
                        "end_ms": subtitle.end_ms,
                        "text": subtitle.text or "",
                        "language": subtitle.language,
                        "confidence": subtitle.confidence,
                    }
                    for subtitle in subtitles
                ],
                "scenes": scene_items,
                "scene_evidence": evidence_items,
                "candidate_boundaries": candidate_boundaries,
                "result_uri": final_artifact.uri if final_artifact else None,
            }
        ).model_dump()
