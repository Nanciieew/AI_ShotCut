"""
Artifact repository — synchronous CRUD.
"""

from sqlalchemy.orm import Session

from core.database.models import Artifact, ModelRun


class ArtifactRepository:
    """Sync repository for Artifact records."""

    def __init__(self, session: Session) -> None:
        self._session = session

    def create(
        self,
        *,
        artifact_id: str,
        project_id: str,
        video_id: str,
        producer_run_id: str,
        artifact_type: str,
        uri: str,
        format: str,
        mime_type: str | None = None,
        size_bytes: int | None = None,
        schema_version: str = "1.0",
        sha256: str | None = None,
        metadata_json: dict | None = None,
    ) -> Artifact:
        artifact = Artifact(
            artifact_id=artifact_id,
            project_id=project_id,
            video_id=video_id,
            producer_run_id=producer_run_id,
            artifact_type=artifact_type,
            uri=uri,
            format=format,
            mime_type=mime_type,
            size_bytes=size_bytes,
            schema_version=schema_version,
            sha256=sha256,
            metadata_json=metadata_json,
        )
        self._session.add(artifact)
        return artifact

    def get(self, artifact_id: str) -> Artifact | None:
        return self._session.get(Artifact, artifact_id)

    def list_by_video(self, video_id: str) -> list[Artifact]:
        return (
            self._session.query(Artifact)
            .filter_by(video_id=video_id)
            .order_by(Artifact.created_at)
            .all()
        )

    def get_artifact_for_task(
        self,
        task_id: str,
        video_id: str,
        artifact_type: str,
        model_name: str,
    ) -> Artifact | None:
        return (
            self._session.query(Artifact)
            .join(ModelRun, Artifact.producer_run_id == ModelRun.run_id)
            .filter(
                ModelRun.task_id == task_id,
                ModelRun.model_name == model_name,
                Artifact.video_id == video_id,
                Artifact.artifact_type == artifact_type,
            )
            .order_by(Artifact.created_at.desc())
            .first()
        )
