"""
FastAPI application entry point.

Provides:
  - GET /health/live  — liveness probe (process alive)
  - GET /health/ready — readiness probe (DB, Storage, FFmpeg)
  - GET /health       — legacy alias for /health/ready
"""

import asyncio
import os
import shutil
from datetime import datetime, timezone
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from apps.api.routes import artifacts, results, tasks, videos
from core.database.session import check_db_connection
from core.logging.config import configure_logging
from core.logging.middleware import RequestLoggingMiddleware

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
        description=(
            "Multi-model video analysis backend — shot detection, scene merging, scene scoring."
        ),
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

    # --- Startup recovery: close every stale in-process execution record. ---
    @app.on_event("startup")
    async def _recover_interrupted_tasks():
        try:
            from core.database.models import ModelRun, WorkflowRun
            from core.database.models import Task as TaskModel
            from core.database.session_sync import get_sync_session

            with get_sync_session() as session:
                stuck = (
                    session.query(TaskModel)
                    .filter(TaskModel.status.in_(("PENDING", "QUEUED", "RUNNING")))
                    .all()
                )
                for t in stuck:
                    t.status = "INTERRUPTED"
                    t.error_code = "TASK_INTERRUPTED"
                    t.error_message = (
                        "Task was running when API restarted. "
                        f"Use POST /api/v1/tasks/{t.task_id}/retry to re-run."
                    )
                now = datetime.now(timezone.utc)
                running_workflows = (
                    session.query(WorkflowRun).filter(WorkflowRun.status == "RUNNING").all()
                )
                for workflow in running_workflows:
                    workflow.status = "INTERRUPTED"
                    workflow.finished_at = now
                running_models = session.query(ModelRun).filter(ModelRun.status == "RUNNING").all()
                for model_run in running_models:
                    model_run.status = "FAILED"
                    model_run.error_code = "TASK_INTERRUPTED"
                    model_run.error_message = "API process stopped during model execution"
                    model_run.retryable = True
                    model_run.finished_at = now
                if stuck or running_workflows or running_models:
                    session.commit()
        except Exception:
            pass  # DB not ready yet — safe to skip

    @app.on_event("shutdown")
    async def _shutdown_executor():
        from apps.api.routes.videos import _executor

        _executor.shutdown()

    # --- Routes ---
    app.include_router(videos.router, prefix="/api/v1")
    app.include_router(tasks.router, prefix="/api/v1")
    app.include_router(results.router, prefix="/api/v1")
    app.include_router(artifacts.router, prefix="/api/v1")

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

        # Provider Gateway, public ngrok URL, and configured model credentials.
        def check_external_dependencies() -> dict[str, bool | str]:
            import requests

            from core.config import get_settings
            from models.doubao_asr.providers.seedasr import SeedASRProvider
            from models.doubao_vision.providers.seedvision import SeedVisionProvider
            from models.vlm_boundary.providers.deepseek_llm import DeepSeekLLMProvider

            settings = get_settings()
            external: dict[str, bool | str] = {}
            try:
                response = requests.get(
                    settings.provider_internal_url.rstrip("/") + "/health/live",
                    timeout=5,
                )
                external["provider_gateway"] = response.status_code == 200
            except Exception as exc:
                external["provider_gateway"] = f"error: {exc}"
            try:
                response = requests.get(
                    settings.public_base_url.rstrip("/") + "/health/live",
                    headers={"User-Agent": "python-requests/AI-ShotCut-readiness"},
                    timeout=10,
                )
                external["provider_public_url"] = (
                    response.status_code == 200
                    and response.headers.get("content-type", "").startswith("application/json")
                )
            except Exception as exc:
                external["provider_public_url"] = f"error: {exc}"
            try:
                external["doubao_asr"] = SeedASRProvider().health_check()
            except Exception as exc:
                external["doubao_asr"] = f"error: {exc}"
            try:
                external["doubao_vision"] = SeedVisionProvider().health_check()
            except Exception as exc:
                external["doubao_vision"] = f"error: {exc}"
            try:
                provider = DeepSeekLLMProvider(
                    api_key=settings.deepseek_api_key,
                    model=settings.subtitle_llm_model,
                    base_url=settings.subtitle_llm_base_url,
                )
                external["subtitle_llm"] = provider.configured_model_available()
            except Exception as exc:
                external["subtitle_llm"] = f"error: {exc}"
            return external

        checks.update(await asyncio.to_thread(check_external_dependencies))
        all_ok = all(v is True for v in checks.values())
        return {"status": "ok" if all_ok else "degraded", "checks": checks}

    # --- Health: Legacy ---
    @app.get("/health")
    async def health():
        """Legacy health check — delegates to /health/ready."""
        return await health_ready()

    # --- Static files (Web GUI) ---
    static_dir = Path(__file__).parent.parent / "static"
    if static_dir.exists():
        app.mount("/", StaticFiles(directory=str(static_dir), html=True), name="static")

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
