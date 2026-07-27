"""
Celery tasks for final result assembly.

Collects all intermediate artifacts and produces the final unified
output: final_result.json.
"""

from workers.celery_app import app


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
