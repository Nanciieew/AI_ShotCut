import asyncio
from types import SimpleNamespace

from apps.api.services.task_service import TaskService


class _Result:
    def __init__(self, *, scalar=None, rows=None):
        self._scalar = scalar
        self._rows = rows or []

    def scalar_one_or_none(self):
        return self._scalar

    def scalars(self):
        return self

    def all(self):
        return self._rows


class _Database:
    def __init__(self, results):
        self._results = iter(results)

    async def execute(self, _statement):
        return next(self._results)


def test_shot_only_success_returns_final_result_without_merge() -> None:
    video_id = "1" * 32
    task_id = "2" * 32
    run_id = "3" * 32
    shot_id = "4" * 32
    video = SimpleNamespace(
        video_id=video_id,
        project_id="5" * 32,
        source_uri="storage://source.mp4",
        normalized_uri="storage://video.mp4",
        audio_uri=None,
        duration_ms=1_000,
        fps_num=24,
        fps_den=1,
        width=320,
        height=180,
        audio_sample_rate=None,
    )
    task = SimpleNamespace(
        task_id=task_id,
        status="SUCCEEDED",
        parameters_json={"scene_analysis": False},
    )
    shot_run = SimpleNamespace(run_id=run_id)
    shot = SimpleNamespace(
        shot_id=shot_id,
        video_id=video_id,
        index=0,
        start_ms=0,
        end_ms=1_000,
        start_frame=0,
        end_frame_exclusive=24,
        boundary_type="hard_cut",
        confidence=1.0,
    )
    database = _Database(
        [
            _Result(scalar=video),
            _Result(scalar=task),
            _Result(scalar=shot_run),
            _Result(rows=[shot]),
        ]
    )

    result = asyncio.run(TaskService().get_video_results(video_id, database))

    assert result["status"] == "SUCCEEDED"
    assert result["result_type"] == "shot_detection"
    assert result["task_id"] == task_id
    assert [item["shot_id"] for item in result["shots"]] == [shot_id]
    assert result["scenes"] == []
    assert result["scene_evidence"] == []
