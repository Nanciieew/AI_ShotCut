"""
Abstract storage backend interface.

All storage implementations (local filesystem, S3, MinIO, OSS, etc.)
must implement this base class.
"""

from abc import ABC, abstractmethod


class BaseStorage(ABC):
    """Abstract storage backend.

    Handles read/write/delete of artifacts, videos, and other binary data.
    """

    @abstractmethod
    async def put(
        self,
        key: str,
        data: bytes,
        content_type: str | None = None,
    ) -> str:
        """Store data and return the URI."""
        ...

    @abstractmethod
    async def get(self, key: str) -> bytes | None:
        """Retrieve data by key. Returns None if not found."""
        ...

    @abstractmethod
    async def delete(self, key: str) -> bool:
        """Delete data by key. Returns True if deleted."""
        ...

    @abstractmethod
    async def exists(self, key: str) -> bool:
        """Check whether a key exists."""
        ...

    @abstractmethod
    async def uri_for(self, key: str) -> str:
        """Return the full URI for a stored key."""
        ...
