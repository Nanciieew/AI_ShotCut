"""
SQLAlchemy ORM models for the Movie Analysis Platform.

These models correspond to the data schemas defined in docs.
Database tables store metadata, task state, and artifact indices.
Actual video/audio/feature files are stored on disk or object storage.
"""

import uuid
from datetime import datetime, timezone
from sqlalchemy import (
    Column,
    String,
    Integer,
    Float,
    Boolean,
    DateTime,
    Text,
    ForeignKey,
    JSON,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


def _uuid() -> str:
    return uuid.uuid4().hex[:16]


def _now() -> datetime:
    return datetime.now(timezone.utc)


# ---------------------------------------------------------------------------
# Base
# ---------------------------------------------------------------------------

class Base(DeclarativeBase):
    pass


# ---------------------------------------------------------------------------
# Project
# ---------------------------------------------------------------------------

class Project(Base):
    __tablename__ = "projects"

    project_id: Mapped[str] = mapped_column(String(32), primary_key=True, default=_uuid)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_now)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=_now, onupdate=_now)

    videos: Mapped[list["Video"]] = relationship(back_populates="project")


# ---------------------------------------------------------------------------
# Video
# ---------------------------------------------------------------------------

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


# ---------------------------------------------------------------------------
# Task
# ---------------------------------------------------------------------------

class Task(Base):
    __tablename__ = "tasks"

    task_id: Mapped[str] = mapped_column(String(32), primary_key=True, default=_uuid)
    video_id: Mapped[str] = mapped_column(
        String(32), ForeignKey("videos.video_id"), nullable=False
    )
    task_type: Mapped[str] = mapped_column(String(64), nullable=False)
    status: Mapped[str] = mapped_column(String(16), default="PENDING")
    stage: Mapped[str] = mapped_column(String(64), nullable=True)
    progress: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_now)
    started_at: Mapped[datetime] = mapped_column(DateTime, nullable=True)
    finished_at: Mapped[datetime] = mapped_column(DateTime, nullable=True)
    error_code: Mapped[str] = mapped_column(String(64), nullable=True)
    error_message: Mapped[str] = mapped_column(Text, nullable=True)
    retry_count: Mapped[int] = mapped_column(Integer, default=0)
    celery_task_id: Mapped[str] = mapped_column(String(128), nullable=True)

    video: Mapped["Video"] = relationship(back_populates="tasks")
    model_runs: Mapped[list["ModelRun"]] = relationship(back_populates="task")


# ---------------------------------------------------------------------------
# Model Run
# ---------------------------------------------------------------------------

class ModelRun(Base):
    __tablename__ = "model_runs"

    run_id: Mapped[str] = mapped_column(String(32), primary_key=True, default=_uuid)
    task_id: Mapped[str] = mapped_column(
        String(32), ForeignKey("tasks.task_id"), nullable=False
    )
    video_id: Mapped[str] = mapped_column(String(32), nullable=False)
    model_name: Mapped[str] = mapped_column(String(64), nullable=False)
    model_version: Mapped[str] = mapped_column(String(32), nullable=False)
    weight_revision: Mapped[str] = mapped_column(String(128), nullable=True)
    code_revision: Mapped[str] = mapped_column(String(128), nullable=True)
    schema_version: Mapped[str] = mapped_column(String(16), nullable=False)
    parameters_json: Mapped[dict] = mapped_column(JSON, nullable=True)
    status: Mapped[str] = mapped_column(String(16), default="PENDING")
    device: Mapped[str] = mapped_column(String(32), nullable=True)
    runtime_ms: Mapped[int] = mapped_column(Integer, nullable=True)
    started_at: Mapped[datetime] = mapped_column(DateTime, nullable=True)
    finished_at: Mapped[datetime] = mapped_column(DateTime, nullable=True)

    task: Mapped["Task"] = relationship(back_populates="model_runs")
    artifacts: Mapped[list["Artifact"]] = relationship(back_populates="model_run")


# ---------------------------------------------------------------------------
# Artifact
# ---------------------------------------------------------------------------

class Artifact(Base):
    __tablename__ = "artifacts"

    artifact_id: Mapped[str] = mapped_column(
        String(32), primary_key=True, default=_uuid
    )
    video_id: Mapped[str] = mapped_column(
        String(32), ForeignKey("videos.video_id"), nullable=False
    )
    run_id: Mapped[str] = mapped_column(
        String(32), ForeignKey("model_runs.run_id"), nullable=False
    )
    artifact_type: Mapped[str] = mapped_column(String(64), nullable=False)
    uri: Mapped[str] = mapped_column(String(1024), nullable=False)
    format: Mapped[str] = mapped_column(String(16), nullable=False)
    schema_version: Mapped[str] = mapped_column(String(16), nullable=False)
    sha256: Mapped[str] = mapped_column(String(64), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_now)

    video: Mapped["Video"] = relationship(back_populates="artifacts")
    model_run: Mapped["ModelRun"] = relationship(back_populates="artifacts")


# ---------------------------------------------------------------------------
# Shot
# ---------------------------------------------------------------------------

class Shot(Base):
    __tablename__ = "shots"

    shot_id: Mapped[str] = mapped_column(String(32), primary_key=True, default=_uuid)
    video_id: Mapped[str] = mapped_column(
        String(32), ForeignKey("videos.video_id"), nullable=False
    )
    index: Mapped[int] = mapped_column(Integer, nullable=False)
    start_ms: Mapped[int] = mapped_column(Integer, nullable=False)
    end_ms: Mapped[int] = mapped_column(Integer, nullable=False)
    start_frame: Mapped[int] = mapped_column(Integer, nullable=True)
    end_frame_exclusive: Mapped[int] = mapped_column(Integer, nullable=True)
    boundary_type: Mapped[str] = mapped_column(String(32), nullable=True)
    confidence: Mapped[float] = mapped_column(Float, nullable=True)

    video: Mapped["Video"] = relationship(back_populates="shots")


# ---------------------------------------------------------------------------
# Subtitle Segment
# ---------------------------------------------------------------------------

class SubtitleSegment(Base):
    __tablename__ = "subtitle_segments"

    subtitle_id: Mapped[str] = mapped_column(
        String(32), primary_key=True, default=_uuid
    )
    video_id: Mapped[str] = mapped_column(
        String(32), ForeignKey("videos.video_id"), nullable=False
    )
    start_ms: Mapped[int] = mapped_column(Integer, nullable=False)
    end_ms: Mapped[int] = mapped_column(Integer, nullable=False)
    text: Mapped[str] = mapped_column(Text, nullable=True)
    language: Mapped[str] = mapped_column(String(16), nullable=True)
    confidence: Mapped[float] = mapped_column(Float, nullable=True)

    video: Mapped["Video"] = relationship(back_populates="subtitles")


# ---------------------------------------------------------------------------
# Scene
# ---------------------------------------------------------------------------

class Scene(Base):
    __tablename__ = "scenes"

    scene_id: Mapped[str] = mapped_column(String(32), primary_key=True, default=_uuid)
    video_id: Mapped[str] = mapped_column(
        String(32), ForeignKey("videos.video_id"), nullable=False
    )
    index: Mapped[int] = mapped_column(Integer, nullable=False)
    start_ms: Mapped[int] = mapped_column(Integer, nullable=False)
    end_ms: Mapped[int] = mapped_column(Integer, nullable=False)
    shot_ids: Mapped[list] = mapped_column(JSON, nullable=True)
    boundary_confidence: Mapped[float] = mapped_column(Float, nullable=True)
    scene_score: Mapped[float] = mapped_column(Float, nullable=True)

    video: Mapped["Video"] = relationship(back_populates="scenes")
    evidence: Mapped[list["SceneEvidence"]] = relationship(back_populates="scene")


# ---------------------------------------------------------------------------
# Scene Evidence
# ---------------------------------------------------------------------------

class SceneEvidence(Base):
    __tablename__ = "scene_evidence"

    evidence_id: Mapped[str] = mapped_column(
        String(32), primary_key=True, default=_uuid
    )
    scene_id: Mapped[str] = mapped_column(
        String(32), ForeignKey("scenes.scene_id"), nullable=False
    )
    visual_continuity: Mapped[float] = mapped_column(Float, nullable=True)
    character_continuity: Mapped[float] = mapped_column(Float, nullable=True)
    location_continuity: Mapped[float] = mapped_column(Float, nullable=True)
    subtitle_continuity: Mapped[float] = mapped_column(Float, nullable=True)
    audio_continuity: Mapped[float] = mapped_column(Float, nullable=True)
    temporal_gap_ms: Mapped[int] = mapped_column(Integer, nullable=True)

    scene: Mapped["Scene"] = relationship(back_populates="evidence")
