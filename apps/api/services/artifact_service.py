"""ArtifactService — wraps StorageService + ArtifactWriter + ArtifactRepository.

All write_artifact calls require a pre-created ModelRun run_id (caller creates
ModelRun first, then passes run_id here). This ensures Artifact FK integrity.
"""

import json
import uuid

from sqlalchemy.orm import Session

from core.artifacts import ArtifactProducer
from core.artifacts.writer import ArtifactWriter
from core.database.models import ModelRunOutput
from core.database.repositories import ArtifactRepository
from core.database.session_sync import get_sync_session
from core.task_storage import STORAGE_ROOT, StorageService, storage_service


def _new_id() -> str:
    return uuid.uuid4().hex


class ArtifactService:
    """Unified artifact facade — paths, I/O, DB records."""

    def __init__(self, svc: StorageService | None = None):
        self.storage = svc or storage_service

    # ---- paths ----------------------------------------------------------

    def build_key(self, pid, vid, tid, model, ver, fn):
        return self.storage.build_key(pid, vid, tid, model, ver, fn)

    def build_uri(self, pid, vid, tid, model, ver, fn):
        return self.storage.build_uri(pid, vid, tid, model, ver, fn)

    def resolve(self, uri):
        return str(self.storage.resolve_local_path(uri))

    def source_dir(self, pid, vid):
        return self.storage.source_dir(pid, vid)

    def task_dir(self, pid, vid, tid):
        return self.storage.task_dir(pid, vid, tid)

    def model_dir(self, pid, vid, tid, model, ver):
        return self.storage.model_dir(pid, vid, tid, model, ver)

    def exists(self, pid, vid, tid, model, ver, fn):
        key = self.build_key(pid, vid, tid, model, ver, fn)
        return self.storage.exists("storage://" + key)

    def read_json(self, pid, vid, tid, model, ver, fn):
        key = self.build_key(pid, vid, tid, model, ver, fn)
        path = self.storage.resolve_local_path("storage://" + key)
        with open(path, encoding="utf-8") as f:
            return json.load(f)

    # ---- artifact write (requires pre-existing ModelRun) ----------------

    def write_artifact(
        self,
        *,
        project_id: str,
        video_id: str,
        task_id: str,
        model_name: str,
        model_version: str,
        filename: str,
        data: dict,
        artifact_type: str,
        run_id: str,  # REQUIRED — caller creates ModelRun first
        mime_type: str = "application/json",
        output_role: str | None = None,
        db_session: Session | None = None,
    ) -> dict:
        """Write JSON artifact to disk + DB.

        Caller MUST create ModelRun (status=RUNNING) before calling this.
        Returns {uri, sha256, artifact_id}.
        """
        key = self.build_key(project_id, video_id, task_id, model_name, model_version, filename)
        uri = "storage://" + key
        artifact_id = _new_id()

        content = json.dumps(data, ensure_ascii=False, indent=2).encode("utf-8")
        result = self.storage.write_artifact_atomic(key, content)
        sha = result["sha256"]

        writer = ArtifactWriter(STORAGE_ROOT)
        producer = ArtifactProducer(model_name=model_name, model_version=model_version)
        writer.write_json_artifact(
            relative_path=key,
            data=data,
            artifact_type=artifact_type,
            artifact_id=artifact_id,
            video_id=video_id,
            run_id=run_id,
            producer=producer,
            schema_version="1.0",
        )

        def persist(session: Session) -> None:
            ArtifactRepository(session).create(
                artifact_id=artifact_id,
                project_id=project_id,
                video_id=video_id,
                producer_run_id=run_id,
                artifact_type=artifact_type,
                uri=uri,
                format="json",
                mime_type=mime_type,
                size_bytes=result["size_bytes"],
                sha256=sha,
            )
            if output_role:
                session.add(
                    ModelRunOutput(
                        run_id=run_id,
                        artifact_id=artifact_id,
                        output_role=output_role,
                    )
                )

        if db_session is not None:
            persist(db_session)
        else:
            with get_sync_session() as session:
                persist(session)
                session.commit()

        return {"uri": uri, "sha256": sha, "artifact_id": artifact_id}

    def register_file_artifact(
        self,
        *,
        project_id: str,
        video_id: str,
        task_id: str,
        model_name: str,
        model_version: str,
        run_id: str,
        filename: str,
        artifact_type: str,
        format: str,
        mime_type: str,
        output_role: str,
        metadata: dict | None = None,
    ) -> dict:
        """Register an existing binary file as an Artifact.

        Computes SHA-256 + size via streaming (never loads full file).
        Writes ONLY a .manifest.json alongside — does NOT overwrite the file.
        Does NOT modify ModelRun status (caller manages lifecycle).
        """
        key = self.build_key(project_id, video_id, task_id, model_name, model_version, filename)
        uri = "storage://" + key
        path = self.storage.resolve_local_path(uri)

        if not path.is_file():
            raise FileNotFoundError(f"File not found: {path}")

        size = path.stat().st_size
        if size == 0:
            raise ValueError(f"File is empty: {path}")

        # Compute SHA-256 in chunks — never read full file into memory
        import hashlib as _hl

        h = _hl.sha256()
        with open(path, "rb") as f:
            while True:
                chunk = f.read(1024 * 1024)  # 1 MB chunks
                if not chunk:
                    break
                h.update(chunk)
        sha = h.hexdigest()
        artifact_id = _new_id()

        # Write manifest JSON alongside the file (does NOT overwrite content)
        import json as _json

        manifest = {
            "schema_version": "1.0",
            "artifact_id": artifact_id,
            "video_id": video_id,
            "run_id": run_id,
            "artifact_type": artifact_type,
            "uri": uri,
            "format": format,
            "mime_type": mime_type,
            "size_bytes": size,
            "sha256": sha,
            "metadata": metadata or {},
        }
        manifest_path = path.with_suffix(path.suffix + ".manifest.json")
        tmp_m = manifest_path.with_suffix(manifest_path.suffix + ".tmp")
        tmp_m.write_text(_json.dumps(manifest, indent=2, ensure_ascii=False), encoding="utf-8")
        tmp_m.replace(manifest_path)

        with get_sync_session() as session:
            ArtifactRepository(session).create(
                artifact_id=artifact_id,
                project_id=project_id,
                video_id=video_id,
                producer_run_id=run_id,
                artifact_type=artifact_type,
                uri=uri,
                format=format,
                mime_type=mime_type,
                size_bytes=size,
                sha256=sha,
                metadata_json=metadata,
            )
            session.add(
                ModelRunOutput(
                    run_id=run_id,
                    artifact_id=artifact_id,
                    output_role=output_role,
                )
            )
            session.commit()

        return {"artifact_id": artifact_id, "uri": uri, "sha256": sha, "size_bytes": size}
