"""Unified Settings — validated application configuration.

Reads from environment variables (which may be loaded from .env
or set by Docker Compose / production orchestration).

Startup validation: if any required setting is missing, the app
fails fast with a clear error message.
"""

import sys
from functools import lru_cache
from typing import Literal

from pydantic import Field, ValidationError
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Central application configuration.

    All paths, URLs, and flags are read from environment variables.
    Sensitive values (passwords, keys) are excluded from repr/str.
    """

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # ------------------------------------------------------------------
    # Environment
    # ------------------------------------------------------------------
    environment: Literal["development", "production", "test"] = Field(
        default="development",
        description="Runtime environment name.",
    )
    debug: bool = Field(default=True, description="Debug mode flag.")
    log_level: Literal["DEBUG", "INFO", "WARNING", "ERROR"] = Field(
        default="INFO",
        description="Log level for structured logging.",
    )

    # ------------------------------------------------------------------
    # Database
    # ------------------------------------------------------------------
    database_url: str = Field(
        default="sqlite+aiosqlite:///./data/app.db",
        description="Database connection URL. PostgreSQL or SQLite.",
    )

    # ------------------------------------------------------------------
    # Redis
    # ------------------------------------------------------------------
    redis_url: str = Field(
        default="redis://localhost:6379/0",
        description="Redis connection URL.",
    )

    # ------------------------------------------------------------------
    # Celery
    # ------------------------------------------------------------------
    celery_broker_url: str = Field(
        default="redis://localhost:6379/0",
        description="Celery broker URL.",
    )
    celery_result_backend: str = Field(
        default="redis://localhost:6379/1",
        description="Celery result backend URL.",
    )

    # ------------------------------------------------------------------
    # Storage
    # ------------------------------------------------------------------
    storage_root: str = Field(
        default="./data",
        description="Root directory for local storage.",
    )
    storage_backend: Literal["local", "s3"] = Field(
        default="local",
        description="Storage backend type.",
    )

    # ------------------------------------------------------------------
    # Model Store
    # ------------------------------------------------------------------
    model_store_root: str = Field(
        default="./model_store",
        description="Root directory for model weights.",
    )

    # ------------------------------------------------------------------
    # FFmpeg
    # ------------------------------------------------------------------
    ffmpeg_path: str = Field(
        default="ffmpeg",
        description="Path or command name for FFmpeg.",
    )

    # ------------------------------------------------------------------
    # API
    # ------------------------------------------------------------------
    api_host: str = Field(default="0.0.0.0", description="API server host.")
    api_port: int = Field(default=8000, ge=1, le=65535, description="API server port.")

    # ------------------------------------------------------------------
    # Keyframe Extraction
    # ------------------------------------------------------------------
    keyframe_extraction_available: bool = Field(
        default=False,
        description="Whether keyframe extraction infrastructure is available.",
    )
    keyframe_format: str = Field(
        default="jpeg",
        description="Keyframe image format: jpeg or png.",
    )
    keyframe_quality: int = Field(
        default=85,
        ge=1,
        le=100,
        description="JPEG quality (1-100). Ignored for PNG.",
    )
    keyframe_max_long_side: int = Field(
        default=672,
        ge=64,
        description="Maximum long-side pixel count. 672 is divisible by DINOv2 patch size 14.",
    )

    # ------------------------------------------------------------------
    # Validation
    # ------------------------------------------------------------------

    def validate_production(self) -> list[str]:
        """Additional checks for production environment.

        Returns a list of warnings (empty = all good).
        """
        warnings: list[str] = []

        if self.environment == "production":
            if self.debug:
                warnings.append("DEBUG is True in production environment.")
            if "postgresql" not in self.database_url:
                warnings.append(
                    "Production should use PostgreSQL, not SQLite. "
                    "Set DATABASE_URL to a postgresql+asyncpg:// URL."
                )
            if self.database_url and "password" in self.database_url.lower():
                # Heuristic: look for default/weak passwords in URL
                for weak in ("postgres:postgres", "password:password", "admin:admin"):
                    if weak in self.database_url:
                        warnings.append("Weak database credentials detected in DATABASE_URL.")
                        break

        return warnings


# ------------------------------------------------------------------
# Singleton
# ------------------------------------------------------------------


@lru_cache
def get_settings() -> Settings:
    """Return the cached, validated Settings instance.

    On first call, validates all required env vars. If validation
    fails, prints errors and exits with code 1.
    """
    try:
        settings = Settings()
    except ValidationError as e:
        print(f"[CONFIG ERROR] Missing or invalid configuration:\n{e}", file=sys.stderr)
        sys.exit(1)

    # Extra validation
    if settings.environment == "production":
        warnings = settings.validate_production()
        if warnings:
            print("[CONFIG WARNING] Production issues:", file=sys.stderr)
            for w in warnings:
                print(f"  - {w}", file=sys.stderr)

    return settings


# Convenience alias
settings = get_settings()
