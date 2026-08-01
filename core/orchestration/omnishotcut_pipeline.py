"""OmniShotCut pipeline canvas builder.

Builds the Celery chain for the core analysis pipeline:

    video.normalize → shot.detect → [video.extract_keyframes] → final.pipeline_complete

All chain links use immutable signatures so that no upstream return value
is injected into the next task's positional arguments.  Each task resolves
its own inputs from the database via task_id / video_id.
"""

from celery import chain

from workers.celery_app import get_celery_app


def build_omnishotcut_canvas(
    *,
    task_id: str,
    video_id: str,
    extract_keyframes: bool = False,
) -> chain:
    """Build the OmniShotCut analysis pipeline canvas.

    Parameters
    ----------
    task_id : str
        App-level task identifier shared by all steps.
    video_id : str
        Video to process.
    extract_keyframes : bool
        When True, insert the keyframe extraction step after shot detection.
        Default False (西游 pipeline does not activate this yet).

    Returns
    -------
    chain
        A Celery chain signature ready for .apply_async().
    """
    app = get_celery_app()

    steps: list = [
        app.signature(
            "video.normalize",
            args=(task_id, video_id),
            immutable=True,
            queue="video",
        ),
        app.signature(
            "shot.detect",
            args=(task_id, video_id, "omnishotcut"),
            immutable=True,
            queue="shot",
        ),
    ]

    if extract_keyframes:
        steps.append(
            app.signature(
                "video.extract_keyframes",
                args=(task_id, video_id),
                immutable=True,
                queue="video",
            )
        )

    steps.append(
        app.signature(
            "final.pipeline_complete",
            args=(task_id, video_id),
            immutable=True,
            queue="final",
        )
    )

    return chain(*steps)
