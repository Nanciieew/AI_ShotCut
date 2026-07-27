"""Artifact writer — atomic write with manifest generation."""

import hashlib
import json
import os
from pathlib import Path
from typing import Any, Optional

from core.artifacts.manifest import (
    ArtifactManifest,
    ArtifactInputRef,
    ArtifactOutputRef,
    ArtifactProducer,
)


class ArtifactWriter:
    """Writes artifact files atomically and generates companion manifests."""

    def __init__(self, storage_root: str) -> None:
        self._root = Path(storage_root).resolve()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def write_json_artifact(
        self,
        *,
        relative_path: str,
        data: Any,
        artifact_type: str,
        artifact_id: str,
        video_id: str,
        run_id: str,
        producer: ArtifactProducer,
        input_ref: Optional[ArtifactInputRef] = None,
        parameters: Optional[dict[str, Any]] = None,
        schema_version: str = "1.0",
    ) -> ArtifactManifest:
        """Write a JSON artifact + its manifest, atomically.

        Returns the ArtifactManifest that was written.
        """
        content = json.dumps(data, ensure_ascii=False, indent=2).encode("utf-8")
        return self._write(
            relative_path=relative_path,
            content=content,
            artifact_type=artifact_type,
            artifact_id=artifact_id,
            video_id=video_id,
            run_id=run_id,
            producer=producer,
            input_ref=input_ref,
            parameters=parameters,
            schema_version=schema_version,
        )

    def write_bytes_artifact(
        self,
        *,
        relative_path: str,
        content: bytes,
        artifact_type: str,
        artifact_id: str,
        video_id: str,
        run_id: str,
        producer: ArtifactProducer,
        input_ref: Optional[ArtifactInputRef] = None,
        parameters: Optional[dict[str, Any]] = None,
        schema_version: str = "1.0",
    ) -> ArtifactManifest:
        """Write a binary artifact + its manifest, atomically."""
        return self._write(
            relative_path=relative_path,
            content=content,
            artifact_type=artifact_type,
            artifact_id=artifact_id,
            video_id=video_id,
            run_id=run_id,
            producer=producer,
            input_ref=input_ref,
            parameters=parameters,
            schema_version=schema_version,
        )

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    def _write(
        self,
        relative_path: str,
        content: bytes,
        artifact_type: str,
        artifact_id: str,
        video_id: str,
        run_id: str,
        producer: ArtifactProducer,
        input_ref: Optional[ArtifactInputRef],
        parameters: Optional[dict[str, Any]],
        schema_version: str,
    ) -> ArtifactManifest:
        full_path = self._resolve(relative_path)
        full_path.parent.mkdir(parents=True, exist_ok=True)

        file_sha256 = hashlib.sha256(content).hexdigest()
        filename = full_path.name

        # Write artifact to temp file, then atomic rename
        tmp_path = full_path.with_suffix(full_path.suffix + ".tmp")
        tmp_path.write_bytes(content)

        # Build manifest
        manifest = ArtifactManifest(
            artifact_type=artifact_type,
            schema_version=schema_version,
            artifact_id=artifact_id,
            video_id=video_id,
            run_id=run_id,
            producer=producer,
            input=input_ref or ArtifactInputRef(),
            output=ArtifactOutputRef(
                file=filename,
                sha256=file_sha256,
                record_count=self._count_records(content, artifact_type),
                size_bytes=len(content),
            ),
            parameters=parameters or {},
        )

        # Write manifest to temp file
        manifest_json = manifest.model_dump_json(indent=2).encode("utf-8")
        manifest_path = full_path.with_suffix(full_path.suffix + ".manifest.json")
        manifest_tmp = manifest_path.with_suffix(manifest_path.suffix + ".tmp")
        manifest_tmp.write_bytes(manifest_json)

        # Atomic rename both
        tmp_path.rename(full_path)
        manifest_tmp.rename(manifest_path)

        return manifest

    def _resolve(self, relative_path: str) -> Path:
        resolved = (self._root / relative_path).resolve()
        if not str(resolved).startswith(str(self._root)):
            raise ValueError(f"Path escapes storage root: {relative_path}")
        return resolved

    @staticmethod
    def _count_records(content: bytes, artifact_type: str) -> Optional[int]:
        """Try to count records for JSON artifacts."""
        try:
            data = json.loads(content)
            # Common array-key patterns
            for key in (
                "shots",
                "subtitle_segments",
                "subtitle_segments",
                "scenes",
                "scores",
                "boundaries",
                "evidence",
            ):
                if key in data and isinstance(data[key], list):
                    return len(data[key])
            if isinstance(data, list):
                return len(data)
        except (json.JSONDecodeError, UnicodeDecodeError):
            pass
        return None
