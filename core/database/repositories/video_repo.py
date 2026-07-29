"""
Video repository — synchronous CRUD for Celery workers.
"""

from typing import Optional

from sqlalchemy.orm import Session

from core.database.models import Video, Project


class VideoRepository:
    """Minimal sync repository for Video + Project operations."""

    def __init__(self, session: Session) -> None:
        self._session = session

    # ------------------------------------------------------------------
    # Project
    # ------------------------------------------------------------------

    def ensure_project(self, project_id: str, name: str = "default") -> Project:
        """Get or create a project."""
        proj = self._session.get(Project, project_id)
        if proj is None:
            proj = Project(project_id=project_id, name=name)
            self._session.add(proj)
            self._session.flush()
        return proj

    # ------------------------------------------------------------------
    # Video
    # ------------------------------------------------------------------

    def create(
        self,
        video_id: str,
        project_id: str,
        source_uri: Optional[str] = None,
    ) -> Video:
        video = Video(
            video_id=video_id,
            project_id=project_id,
            source_uri=source_uri,
        )
        self._session.add(video)
        return video

    def get(self, video_id: str) -> Optional[Video]:
        return self._session.get(Video, video_id)

    def update_metadata(
        self,
        video_id: str,
        *,
        duration_ms: Optional[int] = None,
        fps_num: Optional[int] = None,
        fps_den: Optional[int] = None,
        width: Optional[int] = None,
        height: Optional[int] = None,
        audio_sample_rate: Optional[int] = None,
        normalized_uri: Optional[str] = None,
        audio_uri: Optional[str] = None,
    ) -> Optional[Video]:
        """Update video technical metadata after normalization."""
        video = self.get(video_id)
        if video is None:
            return None

        if duration_ms is not None:
            video.duration_ms = duration_ms
        if fps_num is not None:
            video.fps_num = fps_num
        if fps_den is not None:
            video.fps_den = fps_den
        if width is not None:
            video.width = width
        if height is not None:
            video.height = height
        if audio_sample_rate is not None:
            video.audio_sample_rate = audio_sample_rate
        if normalized_uri is not None:
            video.normalized_uri = normalized_uri
        if audio_uri is not None:
            video.audio_uri = audio_uri

        return video
