"""
Celery tasks for shot boundary detection.

Delegates to OmniShotCut (or other shot detectors) via Adapter.
"""

from workers.celery_app import app


@app.task(name="shot.detect", bind=True, max_retries=2)
def detect_shots(self, task_id: str, video_id: str) -> dict:
    """Run shot boundary detection.

    Reads the normalized video from artifact storage, invokes the
    OmniShotCut adapter, and saves shots.json as an artifact.
    """
    # TODO: Implement OmniShotCut adapter call (MVP Phase 4)
    return {
        "task_id": task_id,
        "video_id": video_id,
        "status": "SUCCEEDED",
        "stage": "detect_shots",
        "message": "placeholder — detect_shots not yet implemented",
    }
