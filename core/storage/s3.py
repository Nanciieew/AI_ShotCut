"""
S3-compatible storage backend (placeholder for production use).

Activate by setting STORAGE_BACKEND=s3 and configuring
the S3 credentials via environment variables.
"""

from core.storage.base import BaseStorage


class S3Storage(BaseStorage):
    """S3 / MinIO / OSS storage backend (placeholder).

    Not implemented in MVP. Switch from LocalStorage when
    deploying to production with object storage.
    """

    def __init__(self) -> None:
        raise NotImplementedError(
            "S3Storage is a placeholder for production deployment. "
            "Use LocalStorage during development."
        )

    async def put(self, key: str, data: bytes, content_type: str | None = None) -> str:
        raise NotImplementedError

    async def get(self, key: str) -> bytes | None:
        raise NotImplementedError

    async def delete(self, key: str) -> bool:
        raise NotImplementedError

    async def exists(self, key: str) -> bool:
        raise NotImplementedError

    async def uri_for(self, key: str) -> str:
        raise NotImplementedError
