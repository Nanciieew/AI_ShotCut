"""
DEPRECATED — Whisper/Doubao ASR module removed (2026-08).

This Celery task is no longer functional. The subtitle.transcribe step
has been removed from the pipeline. Recover models/whisper/ from git
history if ASR is needed again in the future.
"""

from core.logging.context import clear_task_context, set_task_context
from core.media.exceptions import NonRetryableTaskError
from workers.celery_app import app


@app.task(name="subtitle.transcribe", bind=True, max_retries=1)
def transcribe(self, task_id: str, video_id: str) -> dict:
    """Generate subtitles via Doubao ASR adapter.

    Reads normalized video, extracts audio, runs ASR, saves subtitles.json.

    Parameters
    ----------
    task_id : str  App-level task identifier.
    video_id : str  Video to process (must have normalized_uri).
    """
    model_name = "whisper"
    set_task_context(task_id=task_id, video_id=video_id, model=model_name)

    # WhisperAdapter removed (2026-08) — this task is non-functional
    clear_task_context()
    raise NonRetryableTaskError("[IMPORT_FAILED] WhisperAdapter removed — models/whisper/ deleted.")
