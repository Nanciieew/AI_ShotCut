"""
SQLAlchemy ORM models for the Movie Analysis Platform.

Per FASTMULTIMODEL_REFACTOR_PLAN §5:
  - UUID 32-char hex, no truncation
  - Project 1─N Video 1─N Task
  - Task 1─N WorkflowRun, Task 1─N ModelRun
  - ModelRun N─N Artifact via model_run_inputs / model_run_outputs
"""

import uuid
from datetime import datetime, timezone

from sqlalchemy import (
    JSON,
    Boolean,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    text,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


def _uuid() -> str:
    return uuid.uuid4().hex  # 32-char hex, no hyphens


def _now() -> datetime:
    return datetime.now(timezone.utc)


class Base(DeclarativeBase):
    pass


# ============================================================================
# Project
# ============================================================================


class Project(Base):
    __tablename__ = "projects"

    project_id: Mapped[str] = mapped_column(String(32), primary_key=True, default=_uuid)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_now)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=_now, onupdate=_now)

    videos: Mapped[list["Video"]] = relationship(back_populates="project")


# ============================================================================
# Video
# ============================================================================


class Video(Base):
    __tablename__ = "videos"

    video_id: Mapped[str] = mapped_column(String(32), primary_key=True, default=_uuid)
    project_id: Mapped[str] = mapped_column(
        String(32), ForeignKey("projects.project_id"), nullable=False
    )
    source_uri: Mapped[str] = mapped_column(String(1024), nullable=True)
    normalized_uri: Mapped[str] = mapped_column(String(1024), nullable=True)
    audio_uri: Mapped[str] = mapped_column(String(1024), nullable=True)
    duration_ms: Mapped[int] = mapped_column(Integer, nullable=True)
    fps_num: Mapped[int] = mapped_column(Integer, nullable=True)
    fps_den: Mapped[int] = mapped_column(Integer, nullable=True)
    width: Mapped[int] = mapped_column(Integer, nullable=True)
    height: Mapped[int] = mapped_column(Integer, nullable=True)
    audio_sample_rate: Mapped[int] = mapped_column(Integer, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_now)

    project: Mapped["Project"] = relationship(back_populates="videos")
    tasks: Mapped[list["Task"]] = relationship(back_populates="video")
    shots: Mapped[list["Shot"]] = relationship(back_populates="video")
    subtitles: Mapped[list["SubtitleSegment"]] = relationship(back_populates="video")
    scenes: Mapped[list["Scene"]] = relationship(back_populates="video")
    artifacts: Mapped[list["Artifact"]] = relationship(back_populates="video")


# ============================================================================
# Task
# ============================================================================


class Task(Base):
    __tablename__ = "tasks"
    __table_args__ = (
        Index("idx_tasks_video_status", "video_id", "created_at"),
        Index("idx_tasks_status", "status", "created_at"),
    )

    task_id: Mapped[str] = mapped_column(String(32), primary_key=True, default=_uuid)
    project_id: Mapped[str] = mapped_column(
        String(32), ForeignKey("projects.project_id"), nullable=False
    )
    video_id: Mapped[str] = mapped_column(String(32), ForeignKey("videos.video_id"), nullable=False)
    workflow_run_id: Mapped[str | None] = mapped_column(
        String(32),
        ForeignKey(
            "workflow_runs.workflow_run_id",
            name="fk_tasks_workflow_run",
            use_alter=True,
        ),
        nullable=True,
    )
    retry_of_task_id: Mapped[str | None] = mapped_column(
        String(32),
        ForeignKey("tasks.task_id", name="fk_tasks_retry_of"),
        nullable=True,
        index=True,
    )
    task_type: Mapped[str] = mapped_column(String(64), nullable=False)
    status: Mapped[str] = mapped_column(String(16), default="PENDING")
    stage: Mapped[str] = mapped_column(String(64), nullable=True)
    progress: Mapped[int] = mapped_column(Integer, default=0)
    parameters_json: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    executor_run_id: Mapped[str] = mapped_column(String(128), nullable=True)
    retry_count: Mapped[int] = mapped_column(Integer, default=0)
    error_code: Mapped[str] = mapped_column(String(64), nullable=True)
    error_message: Mapped[str] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_now)
    started_at: Mapped[datetime] = mapped_column(DateTime, nullable=True)
    finished_at: Mapped[datetime] = mapped_column(DateTime, nullable=True)

    video: Mapped["Video"] = relationship(back_populates="tasks")
    model_runs: Mapped[list["ModelRun"]] = relationship(back_populates="task")


# ============================================================================
# WorkflowRun
# ============================================================================


class WorkflowRun(Base):
    __tablename__ = "workflow_runs"
    __table_args__ = (Index("idx_workflow_runs_task", "task_id", "started_at"),)

    workflow_run_id: Mapped[str] = mapped_column(String(32), primary_key=True, default=_uuid)
    task_id: Mapped[str] = mapped_column(String(32), ForeignKey("tasks.task_id"), nullable=False)
    workflow_name: Mapped[str] = mapped_column(String(64), nullable=False)
    workflow_version: Mapped[str] = mapped_column(String(16), nullable=False)
    status: Mapped[str] = mapped_column(String(16), default="PENDING")
    started_at: Mapped[datetime] = mapped_column(DateTime, nullable=True)
    finished_at: Mapped[datetime] = mapped_column(DateTime, nullable=True)


# ============================================================================
# ModelRun
# ============================================================================


class ModelRun(Base):
    __tablename__ = "model_runs"
    __table_args__ = (
        Index("idx_model_runs_task", "task_id", "model_name", "status"),
        Index("idx_model_runs_cache", "cache_key", "status"),
        Index(
            "uq_cache_key_active",
            "cache_key",
            unique=True,
            postgresql_where=text("status IN ('RUNNING', 'SUCCEEDED') AND cache_key IS NOT NULL"),
        ),
    )

    run_id: Mapped[str] = mapped_column(String(32), primary_key=True, default=_uuid)
    task_id: Mapped[str] = mapped_column(String(32), ForeignKey("tasks.task_id"), nullable=False)
    video_id: Mapped[str] = mapped_column(String(32), ForeignKey("videos.video_id"), nullable=False)
    model_name: Mapped[str] = mapped_column(String(64), nullable=False)
    model_version: Mapped[str] = mapped_column(String(32), nullable=False)
    code_revision: Mapped[str] = mapped_column(String(128), nullable=True)
    weight_revision: Mapped[str] = mapped_column(String(128), nullable=True)
    schema_version: Mapped[str] = mapped_column(String(16), nullable=False)
    parameters_json: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    cache_key: Mapped[str] = mapped_column(String(128), nullable=True)
    status: Mapped[str] = mapped_column(String(16), default="PENDING")
    runtime_ms: Mapped[int] = mapped_column(Integer, nullable=True)
    device: Mapped[str] = mapped_column(String(32), nullable=True)
    error_code: Mapped[str] = mapped_column(String(64), nullable=True)
    error_message: Mapped[str] = mapped_column(Text, nullable=True)
    retryable: Mapped[bool] = mapped_column(nullable=True)
    started_at: Mapped[datetime] = mapped_column(DateTime, nullable=True)
    finished_at: Mapped[datetime] = mapped_column(DateTime, nullable=True)

    task: Mapped["Task"] = relationship(back_populates="model_runs")
    artifacts: Mapped[list["Artifact"]] = relationship(back_populates="model_run")
    input_refs: Mapped[list["ModelRunInput"]] = relationship(back_populates="model_run")
    output_refs: Mapped[list["ModelRunOutput"]] = relationship(back_populates="model_run")
    scenes: Mapped[list["Scene"]] = relationship(back_populates="producer_run")
    candidate_boundaries: Mapped[list["CandidateBoundary"]] = relationship(
        back_populates="producer_run"
    )


# ============================================================================
# ModelRunInput / ModelRunOutput
# ============================================================================


class ModelRunInput(Base):
    __tablename__ = "model_run_inputs"
    __table_args__ = (
        UniqueConstraint("run_id", "artifact_id", "input_role", name="uq_model_run_inputs"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    run_id: Mapped[str] = mapped_column(String(32), ForeignKey("model_runs.run_id"), nullable=False)
    artifact_id: Mapped[str] = mapped_column(
        String(32), ForeignKey("artifacts.artifact_id"), nullable=False
    )
    input_role: Mapped[str] = mapped_column(String(64), nullable=True)

    model_run: Mapped["ModelRun"] = relationship(back_populates="input_refs")


class ModelRunOutput(Base):
    __tablename__ = "model_run_outputs"
    __table_args__ = (
        UniqueConstraint("run_id", "artifact_id", "output_role", name="uq_model_run_outputs"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    run_id: Mapped[str] = mapped_column(String(32), ForeignKey("model_runs.run_id"), nullable=False)
    artifact_id: Mapped[str] = mapped_column(
        String(32), ForeignKey("artifacts.artifact_id"), nullable=False
    )
    output_role: Mapped[str] = mapped_column(String(64), nullable=True)

    model_run: Mapped["ModelRun"] = relationship(back_populates="output_refs")


# ============================================================================
# Artifact
# ============================================================================


class Artifact(Base):
    __tablename__ = "artifacts"
    __table_args__ = (
        Index("idx_artifacts_video_type", "video_id", "artifact_type", "created_at"),
        Index("idx_artifacts_producer", "producer_run_id"),
    )

    artifact_id: Mapped[str] = mapped_column(String(32), primary_key=True, default=_uuid)
    project_id: Mapped[str] = mapped_column(
        String(32), ForeignKey("projects.project_id"), nullable=False
    )
    video_id: Mapped[str] = mapped_column(String(32), ForeignKey("videos.video_id"), nullable=False)
    producer_run_id: Mapped[str] = mapped_column(
        String(32), ForeignKey("model_runs.run_id"), nullable=False
    )
    artifact_type: Mapped[str] = mapped_column(String(64), nullable=False)
    uri: Mapped[str] = mapped_column(String(1024), nullable=False)
    format: Mapped[str] = mapped_column(String(16), nullable=False)
    mime_type: Mapped[str] = mapped_column(String(64), nullable=True)
    size_bytes: Mapped[int] = mapped_column(Integer, nullable=True)
    sha256: Mapped[str] = mapped_column(String(64), nullable=True)
    schema_version: Mapped[str] = mapped_column(String(16), nullable=False)
    metadata_json: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_now)

    video: Mapped["Video"] = relationship(back_populates="artifacts")
    model_run: Mapped["ModelRun"] = relationship(back_populates="artifacts")


# ============================================================================
# Shot
# ============================================================================


class Shot(Base):
    __tablename__ = "shots"
    __table_args__ = (
        UniqueConstraint("producer_run_id", "index", name="uq_shots_run_index"),
        Index("idx_shots_video_run_index", "video_id", "producer_run_id", "index"),
    )

    shot_id: Mapped[str] = mapped_column(String(32), primary_key=True, default=_uuid)
    video_id: Mapped[str] = mapped_column(String(32), ForeignKey("videos.video_id"), nullable=False)
    producer_run_id: Mapped[str | None] = mapped_column(
        String(32), ForeignKey("model_runs.run_id"), nullable=True
    )
    index: Mapped[int] = mapped_column(Integer, nullable=False)
    start_ms: Mapped[int] = mapped_column(Integer, nullable=False)
    end_ms: Mapped[int] = mapped_column(Integer, nullable=False)
    start_frame: Mapped[int] = mapped_column(Integer, nullable=True)
    end_frame_exclusive: Mapped[int] = mapped_column(Integer, nullable=True)
    boundary_type: Mapped[str] = mapped_column(String(32), nullable=True)
    confidence: Mapped[float] = mapped_column(Float, nullable=True)

    video: Mapped["Video"] = relationship(back_populates="shots")


# ============================================================================
# CandidateBoundary
# ============================================================================


class CandidateBoundary(Base):
    """Every scored shot boundary produced by one merge ModelRun."""

    __tablename__ = "candidate_boundaries"
    __table_args__ = (
        UniqueConstraint("producer_run_id", "boundary_index", name="uq_boundary_run_index"),
        Index(
            "idx_boundaries_video_run_selected",
            "video_id",
            "producer_run_id",
            "selected",
            "boundary_index",
        ),
    )

    candidate_id: Mapped[str] = mapped_column(String(32), primary_key=True, default=_uuid)
    video_id: Mapped[str] = mapped_column(String(32), ForeignKey("videos.video_id"), nullable=False)
    producer_run_id: Mapped[str] = mapped_column(
        String(32), ForeignKey("model_runs.run_id"), nullable=False
    )
    shot_id: Mapped[str] = mapped_column(String(32), ForeignKey("shots.shot_id"), nullable=False)
    scene_id: Mapped[str | None] = mapped_column(
        String(32), ForeignKey("scenes.scene_id"), nullable=True
    )
    boundary_index: Mapped[int] = mapped_column(Integer, nullable=False)
    timestamp_ms: Mapped[int] = mapped_column(Integer, nullable=False)
    scene_score: Mapped[float] = mapped_column(Float, nullable=False)
    location_continuity: Mapped[float | None] = mapped_column(Float, nullable=True)
    character_continuity: Mapped[float | None] = mapped_column(Float, nullable=True)
    subtitle_continuity: Mapped[float | None] = mapped_column(Float, nullable=True)
    selected: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    selection_rank: Mapped[int | None] = mapped_column(Integer, nullable=True)

    producer_run: Mapped["ModelRun"] = relationship(back_populates="candidate_boundaries")


# ============================================================================
# SubtitleSegment
# ============================================================================


class SubtitleSegment(Base):
    __tablename__ = "subtitle_segments"
    __table_args__ = (
        Index("idx_subtitles_video_run_time", "video_id", "producer_run_id", "start_ms"),
    )

    subtitle_id: Mapped[str] = mapped_column(String(32), primary_key=True, default=_uuid)
    video_id: Mapped[str] = mapped_column(String(32), ForeignKey("videos.video_id"), nullable=False)
    producer_run_id: Mapped[str | None] = mapped_column(
        String(32), ForeignKey("model_runs.run_id"), nullable=True
    )
    start_ms: Mapped[int] = mapped_column(Integer, nullable=False)
    end_ms: Mapped[int] = mapped_column(Integer, nullable=False)
    text: Mapped[str] = mapped_column(Text, nullable=True)
    language: Mapped[str] = mapped_column(String(16), nullable=True)
    confidence: Mapped[float] = mapped_column(Float, nullable=True)

    video: Mapped["Video"] = relationship(back_populates="subtitles")


# ============================================================================
# Scene
# ============================================================================


class Scene(Base):
    __tablename__ = "scenes"
    __table_args__ = (
        UniqueConstraint("producer_run_id", "index", name="uq_scenes_run_index"),
        Index("idx_scenes_video_run_index", "video_id", "producer_run_id", "index"),
    )

    scene_id: Mapped[str] = mapped_column(String(32), primary_key=True, default=_uuid)
    video_id: Mapped[str] = mapped_column(String(32), ForeignKey("videos.video_id"), nullable=False)
    producer_run_id: Mapped[str | None] = mapped_column(
        String(32), ForeignKey("model_runs.run_id"), nullable=True
    )
    index: Mapped[int] = mapped_column(Integer, nullable=False)
    start_ms: Mapped[int] = mapped_column(Integer, nullable=False)
    end_ms: Mapped[int] = mapped_column(Integer, nullable=False)
    shot_ids: Mapped[list | None] = mapped_column(JSON, nullable=True)
    boundary_confidence: Mapped[float] = mapped_column(Float, nullable=True)
    scene_score: Mapped[float] = mapped_column(Float, nullable=True)

    video: Mapped["Video"] = relationship(back_populates="scenes")
    producer_run: Mapped["ModelRun | None"] = relationship(back_populates="scenes")
    evidence: Mapped["SceneEvidence | None"] = relationship(
        back_populates="scene", uselist=False, cascade="all, delete-orphan"
    )


# ============================================================================
# SceneEvidence
# ============================================================================


class SceneEvidence(Base):
    __tablename__ = "scene_evidence"
    __table_args__ = (UniqueConstraint("scene_id", name="uq_scene_evidence_scene"),)

    evidence_id: Mapped[str] = mapped_column(String(32), primary_key=True, default=_uuid)
    scene_id: Mapped[str] = mapped_column(String(32), ForeignKey("scenes.scene_id"), nullable=False)
    visual_continuity: Mapped[float] = mapped_column(Float, nullable=True)
    character_continuity: Mapped[float] = mapped_column(Float, nullable=True)
    location_continuity: Mapped[float] = mapped_column(Float, nullable=True)
    subtitle_continuity: Mapped[float] = mapped_column(Float, nullable=True)
    audio_continuity: Mapped[float] = mapped_column(Float, nullable=True)
    temporal_gap_ms: Mapped[int] = mapped_column(Integer, nullable=True)

    scene: Mapped["Scene"] = relationship(back_populates="evidence")
