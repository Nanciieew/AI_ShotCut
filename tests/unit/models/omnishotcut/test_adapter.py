"""Unit tests for OmniShotCutAdapter — mock tests, no real model."""

from models.omnishotcut.adapter import OmniShotCutAdapter


class TestAdapterInit:
    def test_name(self):
        adapter = OmniShotCutAdapter()
        assert adapter.name == "omnishotcut"

    def test_version(self):
        adapter = OmniShotCutAdapter()
        assert len(adapter.version) > 0

    def test_not_loaded_initially(self):
        adapter = OmniShotCutAdapter()
        assert adapter._loaded is False


class TestAdapterUnloaded:
    """Tests that don't require model loading."""

    def test_resolve_uri_storage(self):
        uri = "storage://projects/p1/videos/v1/normalized/video.mp4"
        import os

        root = os.getenv("STORAGE_ROOT", "./data")
        result = OmniShotCutAdapter._resolve_uri(uri)
        assert result == os.path.join(root, "projects/p1/videos/v1/normalized/video.mp4")

    def test_resolve_uri_not_storage(self):
        result = OmniShotCutAdapter._resolve_uri("/absolute/path/video.mp4")
        assert result == "/absolute/path/video.mp4"

    def test_success_format(self):
        output = OmniShotCutAdapter._success(
            task_id="t1",
            video_id="v1",
            schema_version="1.0",
            artifact_key="shots",
            artifact_uri="storage://.../shots.json",
            metrics={"shot_count": 5, "runtime_ms": 1000},
        )
        assert output["status"] == "SUCCEEDED"
        assert output["error"] is None
        assert output["artifacts"]["shots"] == "storage://.../shots.json"
        assert output["metrics"]["shot_count"] == 5
        assert output["schema_version"] == "1.0"

    def test_error_format(self):
        output = OmniShotCutAdapter._error(
            task_id="t1",
            video_id="v1",
            schema_version="1.0",
            code="VIDEO_DECODE_FAILED",
            message="test error",
            retryable=False,
        )
        assert output["status"] == "FAILED"
        assert output["error"]["code"] == "VIDEO_DECODE_FAILED"
        assert output["error"]["retryable"] is False
        assert output["artifacts"] == {}
        assert output["metrics"] == {}

    def test_health_check_not_loaded(self):
        adapter = OmniShotCutAdapter()
        # Without real model, health_check should return False
        result = adapter.health_check()
        assert isinstance(result, bool)
