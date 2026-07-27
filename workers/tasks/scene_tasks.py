"""
Celery tasks for scene boundary detection and scene merging.

Delegates to the Scene Boundary model via Adapter.
"""

from workers.celery_app import app


@app.task(name="scene.detect_boundaries", bind=True, max_retries=2)
def detect_scene_boundaries(self, task_id: str, video_id: str) -> dict:
    """Predict scene boundaries from multi-modal features.

    Reads shots, subtitles, visual embeddings, and audio embeddings
    from artifact storage, invokes the scene boundary model adapter,
    and saves scene_boundaries.json as an artifact.
    """
    # TODO: Implement scene boundary adapter (MVP Phase 7)
    return {
        "task_id": task_id,
        "video_id": video_id,
        "status": "SUCCEEDED",
        "stage": "detect_scene_boundaries",
        "message": "placeholder — detect_scene_boundaries not yet implemented",
    }


@app.task(name="scene.merge_to_scenes", bind=True, max_retries=1)
def merge_shots_to_scenes(self, task_id: str, video_id: str) -> dict:
    """Merge shots into scenes based on predicted boundaries.

    Reads shots.json and scene_boundaries.json, merges adjacent shots
    that are NOT separated by a scene boundary, and saves scenes.json
    as an artifact.
    """
    # TODO: Implement merge logic (MVP Phase 7)
    return {
        "task_id": task_id,
        "video_id": video_id,
        "status": "SUCCEEDED",
        "stage": "merge_shots_to_scenes",
        "message": "placeholder — merge_shots_to_scenes not yet implemented",
    }


@app.task(name="scene.calculate_score", bind=True, max_retries=1)
def calculate_scene_score(self, task_id: str, video_id: str) -> dict:
    """Calculate scene_score for each scene using scene evidence.

    Only scene_score is computed. action_score and plot_score are
    explicitly forbidden per project rules.

    Saves scene_scores.json as an artifact.
    """
    # TODO: Implement scene_score calculation (MVP Phase 8)
    return {
        "task_id": task_id,
        "video_id": video_id,
        "status": "SUCCEEDED",
        "stage": "calculate_scene_score",
        "message": "placeholder — calculate_scene_score not yet implemented",
    }
