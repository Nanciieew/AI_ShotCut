"""Artifact manifest Pydantic schemas — re-exported from core.artifacts."""

from core.artifacts import (
    ArtifactInputRef,
    ArtifactManifest,
    ArtifactOutputRef,
    ArtifactProducer,
)

__all__ = [
    "ArtifactManifest",
    "ArtifactProducer",
    "ArtifactInputRef",
    "ArtifactOutputRef",
]
