"""Persistent cache for independently reusable subtitle-semantic phases."""

from __future__ import annotations

import json
import re
import uuid
from datetime import datetime, timezone
from typing import Any

from sqlalchemy.exc import IntegrityError

from apps.api.services.artifact_service import ArtifactService
from apps.api.services.cache_service import WorkflowCacheService, canonical_cache_key, hash_json
from core.database.models import ModelRun, ModelRunInput
from core.database.session_sync import get_sync_session


class SubtitleStageCache:
    """Store successful summary/global/local/rescore outputs as traced Artifacts."""

    model_name = "subtitle_semantic"
    model_version = "1.1.0"

    def __init__(
        self,
        *,
        project_id: str,
        video_id: str,
        task_id: str,
        input_artifact_ids: dict[str, str],
        model_identity: dict[str, str],
        artifacts: ArtifactService,
        cache: WorkflowCacheService,
    ) -> None:
        self.project_id = project_id
        self.video_id = video_id
        self.task_id = task_id
        self.input_artifact_ids = input_artifact_ids
        self.model_identity = model_identity
        self.artifacts = artifacts
        self.cache = cache

    def get(self, stage: str, payload: dict[str, Any]) -> dict[str, Any] | None:
        key = self._key(stage, payload)
        hit = self.cache.find(video_id=self.video_id, cache_key=key, required_roles={"result"})
        if hit is None:
            return None
        with open(self.artifacts.resolve(hit.outputs["result"].uri), encoding="utf-8") as file:
            return json.load(file)

    def put(self, stage: str, payload: dict[str, Any], data: dict[str, Any]) -> None:
        key = self._key(stage, payload)
        if self.cache.find(video_id=self.video_id, cache_key=key, required_roles={"result"}):
            return
        run_id = uuid.uuid4().hex
        with get_sync_session() as session:
            session.add(
                ModelRun(
                    run_id=run_id,
                    task_id=self.task_id,
                    video_id=self.video_id,
                    model_name=self.model_name,
                    model_version=self.model_version,
                    schema_version="1.0",
                    parameters_json={"phase": stage, "model": self.model_identity},
                    cache_key=key,
                    status="RUNNING",
                    device="remote_api",
                    started_at=datetime.now(timezone.utc),
                )
            )
            for role, artifact_id in self.input_artifact_ids.items():
                session.add(ModelRunInput(run_id=run_id, artifact_id=artifact_id, input_role=role))
            try:
                session.flush()
            except IntegrityError:
                session.rollback()
                return
            filename_stage = re.sub(r"[^a-zA-Z0-9_-]+", "_", stage)[:60]
            self.artifacts.write_artifact(
                project_id=self.project_id,
                video_id=self.video_id,
                task_id=self.task_id,
                model_name=self.model_name,
                model_version=self.model_version,
                run_id=run_id,
                filename=f"cache_{filename_stage}_{key[:12]}.json",
                data=data,
                artifact_type="subtitle_semantic_stage",
                output_role="result",
                db_session=session,
            )
            model_run = session.get(ModelRun, run_id)
            if model_run is None:
                raise RuntimeError(f"Subtitle stage ModelRun {run_id} disappeared")
            model_run.status = "SUCCEEDED"
            model_run.finished_at = datetime.now(timezone.utc)
            session.commit()

    def _key(self, stage: str, payload: dict[str, Any]) -> str:
        return canonical_cache_key(
            stage=f"subtitle.semantic.{stage}",
            model_name=self.model_name,
            model_version=self.model_version,
            inputs={"payload": hash_json(payload)},
            parameters=self.model_identity,
            implementation="subtitle-semantic-stage-cache-v1",
        )
