"""
Celery tasks for subtitle generation / parsing.

Delegates to Whisper (or file parser) via Adapter.
"""

from workers.celery_app import app


@app.task(name="subtitle.transcribe", bind=True, max_retries=2)
def transcribe(self, task_id: str, video_id: str) -> dict:
    """Generate subtitles from audio.

    Priority:
      1. Parse existing subtitle file (SRT, ASS, WebVTT) if provided.
      2. Run Whisper transcription on the extracted audio track.

    Saves subtitles.json as an artifact.
    """
    # TODO: Implement Whisper adapter call (MVP Phase 5)
    return {
        "task_id": task_id,
        "video_id": video_id,
        "status": "SUCCEEDED",
        "stage": "transcribe",
        "message": "placeholder — transcribe not yet implemented",
    }
