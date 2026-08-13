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
    api_host: str = Field(default="127.0.0.1", description="API server host.")
    api_port: int = Field(default=8080, ge=1, le=65535, description="API server port.")
    default_project_id: str = Field(
        default="00000000000000000000000000000000",
        description="Project used by the single-project web upload experience.",
    )

    # ------------------------------------------------------------------
    # VLM / LLM API
    # ------------------------------------------------------------------
    deepseek_api_key: str = Field(
        default="",
        description="API key for DeepSeek (modelarts-maas). "
        "Must be set via DEEPSEEK_API_KEY env var. Never hardcode in code.",
    )
    subtitle_llm_model: str = Field(
        default="deepseek-v4-flash",
        description="Model ID used by subtitle semantic analysis.",
    )
    subtitle_llm_base_url: str = Field(
        default="https://api.modelarts-maas.com/v1/chat/completions",
        description="OpenAI-compatible subtitle semantic chat-completions URL.",
    )
    subtitle_semantic_global_limit: int = Field(default=10, ge=1, le=10)
    subtitle_semantic_local_limit: int = Field(default=5, ge=1, le=5)
    subtitle_semantic_summary_chunk_chars: int = Field(default=12_000, ge=1000)
    subtitle_semantic_summary_chunk_duration_ms: int = Field(default=900_000, ge=60_000)
    subtitle_semantic_context_ms: int = Field(default=90_000, ge=10_000)
    subtitle_semantic_rescore_batch_size: int = Field(default=20, ge=1, le=50)
    subtitle_semantic_local_concurrency: int = Field(default=3, ge=1, le=4)
    subtitle_semantic_max_snap_ms: int = Field(default=8_000, ge=0)
    subtitle_semantic_max_snap_shots: int = Field(default=2, ge=0, le=10)

    # ------------------------------------------------------------------
    # Doubao SeedASR API (Volcano Engine OpenSpeech)
    # ------------------------------------------------------------------
    volc_app_id: str = Field(
        default="",
        description="Volcano Engine APP ID for SeedASR. "
        "Must be set via VOLC_APP_ID env var. Never hardcode in code.",
    )
    volc_access_token: str = Field(
        default="",
        description="Volcano Engine Access Token for SeedASR. "
        "Must be set via VOLC_ACCESS_TOKEN env var. Never hardcode in code.",
    )
    volc_vision_api_key: str = Field(
        default="",
        description="API key for Doubao-Seed-1.6-vision via Volcano Ark. "
        "Format: api-key-{ts}: {uuid}. "
        "Must be set via VOLC_VISION_API_KEY env var. Never hardcode in code.",
    )
    public_base_url: str = Field(
        default="",
        description="Publicly reachable base URL for provider artifact access. "
        "Must use HTTPS. Set via PUBLIC_BASE_URL env var.",
    )
    artifact_signing_secret: str = Field(
        default="",
        description="Secret key for HMAC artifact URL signing. "
        "Must be at least 32 chars in production. "
        "Must be set via ARTIFACT_SIGNING_SECRET env var.",
    )
    provider_url_ttl_seconds: int = Field(
        default=1800,
        ge=60,
        le=3600,
        description="TTL for provider artifact URLs in seconds (1-3600).",
    )
    provider_internal_url: str = Field(
        default="http://localhost:8001",
        description="Internal Provider Gateway base URL used by readiness checks.",
    )

    # ------------------------------------------------------------------
    # Upload
    # ------------------------------------------------------------------
    upload_max_bytes: int = Field(
        default=2_000_000_000,
        description="Maximum upload file size in bytes (default 2 GB).",
    )
    upload_allowed_containers: list[str] = Field(
        default=["mp4", "mov", "avi", "mkv"],
        description="Allowed video container formats. Extensions are detected via FFprobe.",
    )

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
    keyframe_vlm_max_long_side: int = Field(
        default=320,
        ge=64,
        description="VLM proxy keyframe max long side. 320×180 for Qwen VL API calls. "
        "Reduces tokens ~10× vs 672px, 2h movie finishes in ~3min.",
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
