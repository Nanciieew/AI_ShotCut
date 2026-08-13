"""
Local filesystem storage implementation.

Used during development. Files are stored under `STORAGE_ROOT`
(default: ./data) with the same directory hierarchy expected
by the Artifact URI scheme.
"""

import hashlib
import os
import shutil
from pathlib import Path

from core.storage.base import BaseStorage

_STORAGE_ROOT = os.getenv("STORAGE_ROOT", "./data")


class LocalStorage(BaseStorage):
    """Local filesystem storage backend."""

    def __init__(self, root: str | None = None) -> None:
        self._root = Path(root or _STORAGE_ROOT).resolve()

    def _resolve(self, key: str) -> Path:
        # Keys are relative paths within the storage root.
        # Prevent traversal outside root.
        resolved = (self._root / key).resolve()
        if not resolved.is_relative_to(self._root.resolve()):
            raise ValueError(f"Key escapes storage root: {key}")
        return resolved

    async def put(
        self,
        key: str,
        data: bytes,
        content_type: str | None = None,
    ) -> str:
        path = self._resolve(key)
        path.parent.mkdir(parents=True, exist_ok=True)

        # Write to temp file, then atomic rename
        tmp_path = path.with_suffix(path.suffix + ".tmp")
        tmp_path.write_bytes(data)
        tmp_path.rename(path)

        return self.uri_for(key)  # type: ignore[return-value]

    async def get(self, key: str) -> bytes | None:
        path = self._resolve(key)
        if not path.is_file():
            return None
        return path.read_bytes()

    async def delete(self, key: str) -> bool:
        path = self._resolve(key)
        if not path.exists():
            return False
        if path.is_file():
            path.unlink()
        else:
            shutil.rmtree(path)
        return True

    async def exists(self, key: str) -> bool:
        return self._resolve(key).exists()

    async def uri_for(self, key: str) -> str:
        return f"storage://{key}"

    # ------------------------------------------------------------------
    # Convenience helpers
    # ------------------------------------------------------------------

    def uri_to_local_path(self, uri: str) -> Path:
        """Convert a storage:// URI to an absolute local path.

        Raises ValueError if the URI belongs to a different backend
        or would escape the storage root.
        """
        prefix = "storage://"
        if not uri.startswith(prefix):
            raise ValueError(f"Not a storage URI: {uri}")
        key = uri[len(prefix) :]
        return self._resolve(key)

    @staticmethod
    def sha256_hex(data: bytes) -> str:
        return hashlib.sha256(data).hexdigest()
