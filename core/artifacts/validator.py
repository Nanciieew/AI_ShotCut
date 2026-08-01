"""Artifact validator — verify manifest integrity and schema compliance."""

from pathlib import Path

from core.artifacts.manifest import ArtifactManifest


class ArtifactValidator:
    """Validates artifacts against their manifests."""

    def __init__(self, storage_root: str) -> None:
        self._root = Path(storage_root).resolve()

    def validate(self, relative_path: str) -> dict:
        """Validate an artifact file against its .manifest.json.

        Returns a dict with keys: valid (bool), errors (list[str]).
        """
        errors: list[str] = []
        full_path = self._resolve(relative_path)
        manifest_path = full_path.with_suffix(full_path.suffix + ".manifest.json")

        if not full_path.is_file():
            return {"valid": False, "errors": [f"Artifact not found: {relative_path}"]}

        if not manifest_path.is_file():
            return {
                "valid": False,
                "errors": [f"Manifest not found: {manifest_path.name}"],
            }

        try:
            manifest = ArtifactManifest.model_validate_json(
                manifest_path.read_text(encoding="utf-8")
            )
        except Exception as e:
            return {"valid": False, "errors": [f"Manifest parse error: {e}"]}

        # Verify SHA-256
        import hashlib

        actual_sha256 = hashlib.sha256(full_path.read_bytes()).hexdigest()
        if actual_sha256 != manifest.output.sha256:
            errors.append(
                f"SHA-256 mismatch: expected {manifest.output.sha256}, got {actual_sha256}"
            )

        # Verify schema_version is set
        if not manifest.schema_version:
            errors.append("Missing schema_version in manifest")

        return {"valid": len(errors) == 0, "errors": errors, "manifest": manifest}

    def _resolve(self, relative_path: str) -> Path:
        resolved = (self._root / relative_path).resolve()
        if not str(resolved).startswith(str(self._root)):
            raise ValueError(f"Path escapes storage root: {relative_path}")
        return resolved
