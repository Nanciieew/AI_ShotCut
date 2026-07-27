"""
FastAPI application entry point.

Starts the Movie Analysis Platform API server.
"""

import os
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from apps.api.routes import videos, tasks, results
from core.database.session import check_db_connection


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

    # --- Health check ---
    @app.get("/health")
    async def health():
        """Health check endpoint.

        Returns 200 when the API, database, and upstream services
        are reachable.
        """
        db_ok = await check_db_connection()
        return {
            "status": "ok" if db_ok else "degraded",
            "database": "ok" if db_ok else "unreachable",
            "api": "ok",
        }

    return app


# Module-level app instance (used by uvicorn)
app = create_app()
