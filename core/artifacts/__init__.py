# ============================================================
# Artifact Manifest — file-level metadata alongside artifacts.
# ============================================================
# Every major artifact gets a companion .manifest.json with
# provenance, integrity, and schema version information.

from datetime import datetime, timezone
from typing import Any, Optional

from pydantic import BaseModel, Field


class ArtifactProducer(BaseModel):
    """Identifies the model that produced this artifact."""

    model_name: str = Field(..., description="e.g. omnishotcut, whisper")
    model_version: str = Field(..., description="e.g. 1.0.0, large-v3")
    code_revision: str = Field(
        default="unknown",
        description="Git commit hash of the adapter code",
    )
    weight_revision: str = Field(
        default="unknown",
        description="Checkpoint or weight identifier",
    )


class ArtifactInputRef(BaseModel):
    """Reference to the input that produced this artifact."""

    video_sha256: Optional[str] = Field(
        default=None, description="SHA-256 of the input video file"
    )
    input_artifact_uris: list[str] = Field(
        default_factory=list,
        description="URIs of upstream artifacts consumed",
    )


class ArtifactOutputRef(BaseModel):
    """Metadata about the produced file."""

    file: str = Field(..., description="Output filename, e.g. shots.json")
    sha256: str = Field(..., description="SHA-256 of the final file content")
    record_count: Optional[int] = Field(
        default=None, description="Number of records (shots, segments, etc.)"
    )
    size_bytes: Optional[int] = Field(
        default=None, description="File size in bytes"
    )


class ArtifactManifest(BaseModel):
    """Complete provenance manifest for a single pipeline artifact.

    Stored alongside the artifact as `<filename>.manifest.json`.
    """

    artifact_type: str = Field(
        ..., description="Category: shot_boundaries, subtitles, embeddings, etc."
    )
    schema_version: str = Field(default="1.0", description="Schema version used")
    artifact_id: str = Field(..., description="Matches Artifact.artifact_id in DB")
    video_id: str = Field(..., description="Associated video")
    run_id: str = Field(..., description="ModelRun that produced this")
    producer: ArtifactProducer
    input: ArtifactInputRef = Field(default_factory=ArtifactInputRef)
    output: ArtifactOutputRef
    parameters: dict[str, Any] = Field(
        default_factory=dict, description="Model parameters used"
    )
    created_at: str = Field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat(),
        description="ISO-8601 creation timestamp",
    )
