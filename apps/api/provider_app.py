"""Minimal public ASGI app for external model providers.

Only the signed artifact content endpoint is exposed. The main API, uploads,
task controls, artifact listings, and static files remain private.
"""

from fastapi import FastAPI

from apps.api.routes.artifacts import download_artifact

app = FastAPI(title="Movie Analysis Provider Gateway", docs_url=None, redoc_url=None)

app.add_api_route(
    "/api/v1/artifacts/{artifact_id}/content",
    download_artifact,
    methods=["GET"],
    include_in_schema=False,
)


@app.get("/health/live", include_in_schema=False)
async def health_live() -> dict[str, str]:
    return {"status": "ok"}
