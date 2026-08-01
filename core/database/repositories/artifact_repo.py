"""
Artifact repository — synchronous CRUD for Celery workers.
"""

from sqlalchemy.orm import Session

from core.database.models import Artifact, ModelRun


class ArtifactRepository:
    """Minimal sync repository for Artifact records."""

    def __init__(self, session: Session) -> None:
        self._session = session

    def create(
        self,
        artifact_id: str,
        video_id: str,
        run_id: str,
        artifact_type: str,
        uri: str,
        format: str,
        schema_version: str = "1.0",
        sha256: str | None = None,
    ) -> Artifact:
        artifact = Artifact(
            artifact_id=artifact_id,
            video_id=video_id,
            run_id=run_id,
            artifact_type=artifact_type,
            uri=uri,
            format=format,
            schema_version=schema_version,
            sha256=sha256,
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
        """Get the artifact produced by a specific task's model run.

        Joins Artifact → ModelRun on run_id, filters by task_id + model_name.
        Returns the most recent if multiple exist (retry edge case).

        This is the correct way for downstream tasks to find upstream artifacts —
        it scopes to the same pipeline run, not just the latest for the video.
        """
        return (
            self._session.query(Artifact)
            .join(ModelRun, Artifact.run_id == ModelRun.run_id)
            .filter(
                ModelRun.task_id == task_id,
                ModelRun.model_name == model_name,
                Artifact.video_id == video_id,
                Artifact.artifact_type == artifact_type,
            )
            .order_by(Artifact.created_at.desc())
            .first()
        )
