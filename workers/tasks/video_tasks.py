"""
Celery tasks for video preprocessing.

Handles:
  - Video normalization (FFmpeg)
  - Audio extraction
  - Metadata generation
"""

from workers.celery_app import app


@app.task(name="video.normalize", bind=True, max_retries=3)
def normalize_video(self, task_id: str, video_id: str) -> dict:
    """Normalize an uploaded video to a standard format.

    Steps:
      1. Re-encode to consistent codec / resolution / fps.
      2. Extract audio as 16 kHz mono WAV.
      3. Generate metadata.json with duration, fps, dimensions.

    Input is passed as task_id + video_id; actual video is read from
    artifact storage via its URI.
    """
    # TODO: Implement FFmpeg normalization pipeline (MVP Phase 3)
    return {
        "task_id": task_id,
        "video_id": video_id,
        "status": "SUCCEEDED",
        "stage": "normalize_video",
        "message": "placeholder — normalize_video not yet implemented",
    }
