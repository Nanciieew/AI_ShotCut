"""
FastAPI application entry point.

Provides:
  - GET /health/live  — liveness probe (process alive)
  - GET /health/ready — readiness probe (DB, Redis, Storage, FFmpeg, Celery)
  - GET /health       — legacy alias for /health/ready
"""

import os
import shutil
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from apps.api.routes import videos, tasks, results
from core.database.session import check_db_connection
from core.logging.middleware import RequestLoggingMiddleware
from core.logging.config import configure_logging


# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

configure_logging(
    level=os.getenv("LOG_LEVEL", "INFO"),
    json_output=os.getenv("ENVIRONMENT", "development") == "production",
)


# ---------------------------------------------------------------------------
# Application factory
# ---------------------------------------------------------------------------

def create_app() -> FastAPI:
    """Build and configure the FastAPI application."""

    debug = os.getenv("DEBUG", "true").lower() == "true"

    app = FastAPI(
        title="Movie Analysis Platform",
        description="Multi-model video analysis backend — shot detection, scene merging, scene scoring.",
        version="0.1.0",
        docs_url="/docs" if debug else None,
        redoc_url="/redoc" if debug else None,
    )

    # --- Middleware ---
    app.add_middleware(RequestLoggingMiddleware)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # --- Routes ---
    app.include_router(videos.router, prefix="/api/v1")
    app.include_router(tasks.router, prefix="/api/v1")
    app.include_router(results.router, prefix="/api/v1")

    # --- Health: Liveness (Kubernetes-style) ---
    @app.get("/health/live")
    async def health_live():
        """Liveness probe — only checks the API process is alive."""
        return {"status": "ok"}

    # --- Health: Readiness ---
    @app.get("/health/ready")
    async def health_ready():
        """Readiness probe — checks all upstream dependencies.

        Returns 200 only when all critical services are reachable.
        Returns non-200 status if any dependency is unhealthy.
        """
        checks: dict[str, bool | str] = {}

        # Database
        try:
            checks["database"] = await check_db_connection()
        except Exception as e:
            checks["database"] = f"error: {e}"

        # Redis
        try:
            from workers.celery_app import app as celery_app
            conn = celery_app.broker_connection()
            conn.ensure_connection(max_retries=1, timeout=3)
            checks["redis"] = True
            conn.close()
        except Exception as e:
            checks["redis"] = f"error: {e}"

        # Celery Broker ping
        try:
            from workers.celery_app import app as celery_app
            insp = celery_app.control.inspect()
            stats = insp.ping()
            checks["celery_broker"] = bool(stats)
        except Exception as e:
            checks["celery_broker"] = f"error: {e}"

        # Storage (writable)
        storage_root = os.getenv("STORAGE_ROOT", "./data")
        try:
            test_file = os.path.join(storage_root, ".health_check_write_test")
            with open(test_file, "w") as f:
                f.write("ok")
            os.remove(test_file)
            checks["storage_write"] = True
        except Exception as e:
            checks["storage_write"] = f"error: {e}"

        # FFmpeg
        checks["ffmpeg"] = shutil.which("ffmpeg") is not None

        all_ok = all(v is True for v in checks.values())
        status_code = 200 if all_ok else 503
        return {"status": "ok" if all_ok else "degraded", "checks": checks}

    # --- Health: Legacy ---
    @app.get("/health")
    async def health():
        """Legacy health check — delegates to /health/ready."""
        return await health_ready()

    # --- Model Health (placeholder) ---
    @app.get("/api/v1/models/{model_name}/health")
    async def model_health(model_name: str):
        """Reserved endpoint for per-model health checks.

        Returns NOT_IMPLEMENTED since no models are loaded in MVP.
        """
        return {
            "model_name": model_name,
            "status": "not_loaded",
            "message": "Model health check not yet implemented. Models are not loaded in MVP.",
        }

    return app


# Module-level app instance (used by uvicorn)
app = create_app()
