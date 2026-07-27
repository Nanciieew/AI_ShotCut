"""
Celery tasks for visual and audio feature extraction.

Extracts embeddings per shot or per time window.
"""

from workers.celery_app import app


@app.task(name="feature.extract_visual", bind=True, max_retries=2)
def extract_visual_features(self, task_id: str, video_id: str) -> dict:
    """Extract visual features per shot.

    Saves visual_features.npy as an artifact.
    """
    # TODO: Implement visual encoder adapter (MVP Phase 6)
    return {
        "task_id": task_id,
        "video_id": video_id,
        "status": "SUCCEEDED",
        "stage": "extract_visual_features",
        "message": "placeholder — extract_visual_features not yet implemented",
    }


@app.task(name="feature.extract_audio", bind=True, max_retries=2)
def extract_audio_features(self, task_id: str, video_id: str) -> dict:
    """Extract audio features (RMS, spectral, etc.) per time window.

    Saves audio_features.npy as an artifact.
    """
    # TODO: Implement audio encoder adapter (MVP Phase 6)
    return {
        "task_id": task_id,
        "video_id": video_id,
        "status": "SUCCEEDED",
        "stage": "extract_audio_features",
        "message": "placeholder — extract_audio_features not yet implemented",
    }
