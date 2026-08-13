"""Unified StorageService — path generation, atomic writes, signed URLs.

Path format (§6.1):
  projects/{project_id}/videos/{video_id}/
    source/original.{ext}
    tasks/{task_id}/
      {model_name}/{version}/
        {filename}

URI: storage://projects/{pid}/videos/{vid}/tasks/{tid}/{model}/{version}/{file}

Security: all paths validated against traversal, ID format, and storage root.
"""

import hashlib
import re
from pathlib import Path
from typing import IO

from core.config import get_settings

STORAGE_ROOT = get_settings().storage_root

_ID_PATTERN = re.compile(r"^[a-f0-9]{32}$")


def _validate_id(value: str, label: str) -> None:
    if not _ID_PATTERN.match(value):
        raise ValueError(f"Invalid {label}: {value!r}")


def _safe_filename(name: str) -> str:
    if not re.match(r"^[a-zA-Z0-9._-]+$", name):
        raise ValueError(f"Unsafe filename: {name!r}")
    if name.startswith(".") or ".." in name:
        raise ValueError(f"Path traversal rejected: {name!r}")
    return name


def _resolve(root: Path, *parts: str) -> Path:
    resolved = (root / Path(*parts)).resolve()
    root_resolved = root.resolve()
    if not resolved.is_relative_to(root_resolved):
        raise ValueError(f"Path escapes storage root: {'/'.join(parts)}")
    return resolved


class StorageService:
    """Unified file storage facade — no business code calls Path(STORAGE_ROOT) directly."""

    @staticmethod
    def build_key(
        project_id: str,
        video_id: str,
        task_id: str,
        model_name: str,
        model_version: str,
        filename: str,
    ) -> str:
        for val, label in [
            (project_id, "project_id"),
            (video_id, "video_id"),
            (task_id, "task_id"),
        ]:
            _validate_id(val, label)
        _safe_filename(model_name)
        _safe_filename(model_version)
        _safe_filename(filename)
        return (
            f"projects/{project_id}/videos/{video_id}/"
            f"tasks/{task_id}/{model_name}/{model_version}/{filename}"
        )

    @staticmethod
    def build_uri(
        project_id: str,
        video_id: str,
        task_id: str,
        model_name: str,
        model_version: str,
        filename: str,
    ) -> str:
        return "storage://" + StorageService.build_key(
            project_id, video_id, task_id, model_name, model_version, filename
        )

    @staticmethod
    def resolve_local_path(uri: str) -> Path:
        prefix = "storage://"
        if not uri.startswith(prefix):
            raise ValueError(f"Not a storage URI: {uri!r}")
        key = uri[len(prefix) :]
        return _resolve(Path(STORAGE_ROOT), *key.split("/"))

    @staticmethod
    def put_stream(key: str, stream: IO[bytes], max_bytes: int = 0) -> dict:
        path = _resolve(Path(STORAGE_ROOT), *key.split("/"))
        path.parent.mkdir(parents=True, exist_ok=True)
        tmp = path.with_suffix(path.suffix + ".tmp")
        h = hashlib.sha256()
        size = 0
        with open(tmp, "wb") as f:
            while True:
                chunk = stream.read(65536)
                if not chunk:
                    break
                size += len(chunk)
                if max_bytes and size > max_bytes:
                    tmp.unlink()
                    raise ValueError(f"File exceeds max size {max_bytes}")
                h.update(chunk)
                f.write(chunk)
        tmp.replace(path)
        return {"path": str(path), "size_bytes": size, "sha256": h.hexdigest()}

    @staticmethod
    def write_artifact_atomic(key: str, data: bytes) -> dict:
        path = _resolve(Path(STORAGE_ROOT), *key.split("/"))
        path.parent.mkdir(parents=True, exist_ok=True)
        tmp = path.with_suffix(path.suffix + ".tmp")
        tmp.write_bytes(data)
        sha = hashlib.sha256(data).hexdigest()
        tmp.replace(path)
        return {"path": str(path), "size_bytes": len(data), "sha256": sha}

    @staticmethod
    def open(uri: str) -> Path:
        path = StorageService.resolve_local_path(uri)
        if not path.is_file():
            raise FileNotFoundError(f"Artifact not found: {uri}")
        return path

    @staticmethod
    def exists(uri: str) -> bool:
        try:
            return StorageService.resolve_local_path(uri).exists()
        except ValueError:
            return False

    @staticmethod
    def create_download_url(artifact_id: str, expires_s: int = 3600) -> str:
        from core.security.artifact_tokens import sign_token

        ttl = min(max(1, expires_s), 3600)
        expires_at = int(__import__("time").time()) + ttl
        token = sign_token(
            artifact_id=artifact_id,
            expires_at=expires_at,
            purpose="download",
        )
        from urllib.parse import quote

        return f"/api/v1/artifacts/{artifact_id}/content?token={quote(token, safe='')}"

    @staticmethod
    def create_provider_url(artifact_id: str, project_id: str = "", ttl_s: int = 1800) -> str:
        """Generate a signed short-lived URL for external model providers."""
        from core.config import get_settings
        from core.security.artifact_tokens import sign_token

        settings = get_settings()
        public_base = settings.public_base_url.rstrip("/")
        if not public_base:
            raise RuntimeError("PUBLIC_BASE_URL not set in config/.env")
        if not public_base.startswith("https://"):
            raise RuntimeError("PUBLIC_BASE_URL must use HTTPS")
        ttl = min(ttl_s, settings.provider_url_ttl_seconds)
        expires_at = int(__import__("time").time()) + ttl
        token = sign_token(
            artifact_id=artifact_id,
            expires_at=expires_at,
            purpose="provider",
            project_id=project_id,
        )
        from urllib.parse import quote

        return f"{public_base}/api/v1/artifacts/{artifact_id}/content?token={quote(token, safe='')}"

    @staticmethod
    def task_dir(project_id: str, video_id: str, task_id: str) -> str:
        for val, label in [(project_id, "pid"), (video_id, "vid"), (task_id, "tid")]:
            _validate_id(val, label)
        return str(
            Path(STORAGE_ROOT) / "projects" / project_id / "videos" / video_id / "tasks" / task_id
        )

    @staticmethod
    def source_dir(project_id: str, video_id: str) -> str:
        for val, label in [(project_id, "pid"), (video_id, "vid")]:
            _validate_id(val, label)
        return str(Path(STORAGE_ROOT) / "projects" / project_id / "videos" / video_id / "source")

    @staticmethod
    def model_dir(
        project_id: str,
        video_id: str,
        task_id: str,
        model_name: str,
        model_version: str,
    ) -> str:
        key = StorageService.build_key(
            project_id, video_id, task_id, model_name, model_version, "directory.placeholder"
        )
        d = _resolve(Path(STORAGE_ROOT), *key.split("/")).parent
        d.mkdir(parents=True, exist_ok=True)
        return str(d)


storage_service = StorageService()
