"""Artifact schema — index entry for a saved pipeline artifact."""

from datetime import datetime

from pydantic import BaseModel, Field


class Artifact(BaseModel):
    """Points to a file produced by a model run.

    The actual data lives on disk or object storage; this is the
    database index entry that makes it discoverable and verifiable.
    """

    artifact_id: str = Field(..., description="Unique artifact identifier")
    video_id: str = Field(..., description="Associated video")
    run_id: str = Field(..., description="Model run that produced this artifact")
    artifact_type: str = Field(
        ...,
        description="Category, e.g. shot_boundaries, subtitles, embeddings",
    )
    uri: str = Field(
        ...,
        description="Storage URI, e.g. storage://projects/.../shots.json",
    )
    format: str = Field(..., description="File format: json, npy, npz, mp4, wav")
    schema_version: str = Field(default="1.0", description="Schema version used")
    sha256: str | None = Field(default=None, description="SHA-256 hash for integrity verification")
    created_at: datetime = Field(default_factory=datetime.utcnow)
