"""OmniShotCut pipeline canvas builder.

Builds the Celery chain for video analysis.

Full scene analysis chain:
    video.normalize
      → shot.detect
        → video.extract_keyframes  ──┐
        → subtitle.transcribe       ──┤
          → scene.score_vlm           │ (parallel via group)
          → scene.score_plot          │
            → scene.merge_scores      │
              → final.pipeline_complete

All chain links use immutable signatures. Each task resolves its own
inputs from the database via task_id / video_id.
"""

from celery import chain, group

from workers.celery_app import get_celery_app


def build_omnishotcut_canvas(
    *,
    task_id: str,
    video_id: str,
    extract_keyframes: bool = False,
    scene_analysis: bool = False,
    shot_model: str = "ffmpeg_scene",
    score_mode: str = "weighted",
    location_weight: int = 35,
    character_weight: int = 35,
    plot_weight: int = 30,
) -> chain:
    """Build the OmniShotCut analysis pipeline canvas.

    Parameters
    ----------
    task_id : str
        App-level task identifier shared by all steps.
    video_id : str
        Video to process.
    extract_keyframes : bool
        When True, extract 25%/75% keyframes after shot detection.
    scene_analysis : bool
        When True, run full scene scoring: subtitle transcription,
        VLM + LLM scoring, and final scene merging.
    score_mode : str
        Merge mode: location_only, character_only, plot_only, custom, weighted.
    location_weight : int
        Location weight 1-10 (custom mode only).
    character_weight : int
        Character weight 1-10 (custom mode only).
    plot_weight : int
        Plot weight 1-10 (custom mode only).

    Returns
    -------
    chain
        A Celery chain signature ready for .apply_async().
    """
    app = get_celery_app()

    steps: list = [
        app.signature("video.normalize", args=(task_id, video_id),
                      immutable=True, queue="video"),
        app.signature("shot.detect", args=(task_id, video_id, shot_model),
                      immutable=True, queue="shot"),
    ]

    if scene_analysis:
        # Keyframe extraction (needs shots) + Subtitle (needs normalized video)
        # Run in parallel — independent tasks
        steps.append(
            group(
                app.signature("video.extract_keyframes", args=(task_id, video_id),
                              immutable=True, queue="video"),
                app.signature("subtitle.transcribe", args=(task_id, video_id),
                              immutable=True, queue="subtitle"),
            )
        )
        # VLM (needs keyframes+shots) + Plot (needs subtitles+shots) in parallel
        steps.append(
            group(
                app.signature("scene.score_vlm", args=(task_id, video_id),
                              immutable=True, queue="scene"),
                app.signature("scene.score_plot", args=(task_id, video_id),
                              immutable=True, queue="scene"),
            )
        )
        # Merge after both scoring groups complete
        steps.append(
            app.signature("scene.merge_scores",
                          args=(task_id, video_id, score_mode,
                                location_weight, character_weight, plot_weight),
                          immutable=True, queue="scene")
        )
    elif extract_keyframes:
        steps.append(
            app.signature("video.extract_keyframes", args=(task_id, video_id),
                          immutable=True, queue="video")
        )

    steps.append(
        app.signature("final.pipeline_complete", args=(task_id, video_id),
                      immutable=True, queue="final")
    )

    return chain(*steps)
