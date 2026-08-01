"""
Celery tasks for final result assembly and pipeline completion.

Handles:
  - final.pipeline_complete: marks the overall Task as SUCCEEDED
  - final.assemble: collects artifacts and produces final_result.json (stub)
"""

from core.database.repositories import TaskRepository
from core.database.session_sync import get_sync_session
from core.logging.context import clear_task_context, set_task_context
from workers.celery_app import app


@app.task(name="final.pipeline_complete", bind=True, max_retries=1)
def pipeline_complete(self, task_id: str, video_id: str) -> dict:
    """Finalize the pipeline — mark the overall Task as SUCCEEDED.

    This is the ONLY task that sets the Task status to SUCCEEDED.
    All intermediate tasks (normalize, detect, extract_keyframes, etc.)
    only update their ModelRun and progress — never the Task status.

    Parameters
    ----------
    task_id : str
        App-level task identifier.
    video_id : str
        Video that was processed.
    """
    set_task_context(task_id=task_id, video_id=video_id, model="pipeline_finalizer")

    with get_sync_session() as session:
        task_repo = TaskRepository(session)

        task_repo.update_status(task_id, "SUCCEEDED")
        task_repo.update_progress(task_id, 100, stage="completed")
        session.commit()

    clear_task_context()

    return {
        "task_id": task_id,
        "video_id": video_id,
        "status": "SUCCEEDED",
        "stage": "completed",
        "message": "Pipeline completed successfully",
    }


@app.task(name="final.assemble", bind=True, max_retries=1)
def assemble_final_result(self, task_id: str, video_id: str) -> dict:
    """Assemble final_result.json from all pipeline artifacts.

    Reads:
      - scenes.json
      - scene_scores.json
      - metadata.json

    Produces a single final_result.json artifact containing the
    complete analysis output.
    """
    # TODO: Implement result assembly (MVP Phase 8)
    return {
        "task_id": task_id,
        "video_id": video_id,
        "status": "SUCCEEDED",
        "stage": "assemble_final_result",
        "message": "placeholder — assemble_final_result not yet implemented",
    }
