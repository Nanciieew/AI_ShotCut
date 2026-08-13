"""Content-addressed Workflow cache backed by ModelRun and Artifact lineage."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from core.database.models import Artifact, ModelRun, ModelRunOutput
from core.database.session_sync import get_sync_session
from core.task_storage import StorageService, storage_service

CACHE_SCHEMA_VERSION = "workflow-cache-v1"


def canonical_cache_key(
    *,
    stage: str,
    model_name: str,
    model_version: str,
    inputs: dict[str, str],
    parameters: dict[str, Any],
    implementation: str,
) -> str:
    """Hash a canonical step contract; secrets and task IDs must not be included."""
    payload = {
        "cache_schema": CACHE_SCHEMA_VERSION,
        "stage": stage,
        "model": {"name": model_name, "version": model_version},
        "inputs": inputs,
        "parameters": parameters,
        "implementation": implementation,
    }
    encoded = json.dumps(
        payload,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def hash_file(path: str | Path) -> str:
    digest = hashlib.sha256()
    with open(path, "rb") as file:
        while chunk := file.read(1024 * 1024):
            digest.update(chunk)
    return digest.hexdigest()


def hash_json(value: Any) -> str:
    encoded = json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


@dataclass(frozen=True)
class CachedArtifact:
    artifact_id: str
    artifact_type: str
    uri: str
    sha256: str
    size_bytes: int | None
    metadata: dict[str, Any]


@dataclass(frozen=True)
class CacheHit:
    source_run_id: str
    cache_key: str
    outputs: dict[str, CachedArtifact]


class WorkflowCacheService:
    """Find only complete, immutable and byte-valid cached outputs."""

    def __init__(self, storage: StorageService | None = None) -> None:
        self.storage = storage or storage_service

    def artifact_fingerprint(self, artifact_id: str) -> str:
        with get_sync_session() as session:
            artifact = session.get(Artifact, artifact_id)
            if artifact is None:
                raise RuntimeError(f"Artifact {artifact_id} does not exist")
            return artifact.sha256 or f"uri:{artifact.uri}"

    def artifact(self, artifact_id: str) -> CachedArtifact:
        with get_sync_session() as session:
            artifact = session.get(Artifact, artifact_id)
            if artifact is None:
                raise RuntimeError(f"Artifact {artifact_id} does not exist")
            return self._to_cached_artifact(artifact)

    def find(
        self,
        *,
        video_id: str,
        cache_key: str,
        required_roles: set[str],
        optional_roles: set[str] | None = None,
    ) -> CacheHit | None:
        allowed_roles = required_roles | (optional_roles or set())
        with get_sync_session() as session:
            runs = list(
                session.execute(
                    select(ModelRun)
                    .where(
                        ModelRun.video_id == video_id,
                        ModelRun.cache_key == cache_key,
                        ModelRun.status == "SUCCEEDED",
                    )
                    .order_by(ModelRun.finished_at.desc())
                ).scalars()
            )
            for run in runs:
                rows = session.execute(
                    select(ModelRunOutput.output_role, Artifact)
                    .join(Artifact, Artifact.artifact_id == ModelRunOutput.artifact_id)
                    .where(ModelRunOutput.run_id == run.run_id)
                ).all()
                outputs = {
                    str(role): self._to_cached_artifact(artifact)
                    for role, artifact in rows
                    if role in allowed_roles
                }
                if not required_roles.issubset(outputs):
                    continue
                if all(self._validate_artifact(artifact) for artifact in outputs.values()):
                    return CacheHit(
                        source_run_id=run.run_id,
                        cache_key=cache_key,
                        outputs=outputs,
                    )
        return None

    def promote_legacy_run(self, run_id: str, cache_key: str) -> None:
        """Attach a canonical key to a validated pre-cache successful run."""
        with get_sync_session() as session:
            run = session.get(ModelRun, run_id)
            if run is None or run.status != "SUCCEEDED" or run.cache_key:
                return
            run.cache_key = cache_key
            try:
                session.commit()
            except IntegrityError:
                # Another request may have promoted an equivalent origin first.
                session.rollback()

    @staticmethod
    def cache_metadata(hit: CacheHit) -> dict[str, Any]:
        return {
            "cache_hit": True,
            "source_run_id": hit.source_run_id,
            "source_cache_key": hit.cache_key,
        }

    @staticmethod
    def _to_cached_artifact(artifact: Artifact) -> CachedArtifact:
        return CachedArtifact(
            artifact_id=artifact.artifact_id,
            artifact_type=artifact.artifact_type,
            uri=artifact.uri,
            sha256=artifact.sha256 or "",
            size_bytes=artifact.size_bytes,
            metadata=artifact.metadata_json or {},
        )

    def _validate_artifact(self, artifact: CachedArtifact) -> bool:
        try:
            path = self.storage.resolve_local_path(artifact.uri)
        except (OSError, ValueError):
            return False
        if not path.is_file():
            return False
        if artifact.size_bytes is not None and path.stat().st_size != artifact.size_bytes:
            return False
        return not artifact.sha256 or hash_file(path) == artifact.sha256
