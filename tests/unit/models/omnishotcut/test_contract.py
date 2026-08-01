"""IO_Rule contract tests for OmniShotCut adapter output."""


class TestOutputContract:
    """Verify success/failure output follows IO_Rule §2/§3."""

    SUCCESS_REQUIRED = [
        "schema_version",
        "task_id",
        "video_id",
        "status",
        "model",
        "artifacts",
        "metrics",
        "error",
    ]

    ERROR_REQUIRED = ["code", "message", "retryable"]

    MODEL_REQUIRED = ["name", "version"]

    METRICS_MINIMUM = ["runtime_ms"]

    def test_success_has_all_required_fields(self):
        from models.omnishotcut.adapter import OmniShotCutAdapter

        output = OmniShotCutAdapter._success(
            task_id="t1",
            video_id="v1",
            schema_version="1.0",
            artifact_key="shots",
            artifact_uri="storage://...",
            metrics={"shot_count": 1, "runtime_ms": 100},
        )
        for field in self.SUCCESS_REQUIRED:
            assert field in output, f"Missing field: {field}"

    def test_success_error_is_null(self):
        from models.omnishotcut.adapter import OmniShotCutAdapter

        output = OmniShotCutAdapter._success(
            task_id="t1",
            video_id="v1",
            schema_version="1.0",
            artifact_key="shots",
            artifact_uri="storage://...",
            metrics={"shot_count": 1, "runtime_ms": 100},
        )
        assert output["error"] is None

    def test_success_status_is_succeeded(self):
        from models.omnishotcut.adapter import OmniShotCutAdapter

        output = OmniShotCutAdapter._success(
            task_id="t1",
            video_id="v1",
            schema_version="1.0",
            artifact_key="shots",
            artifact_uri="storage://...",
            metrics={"shot_count": 1, "runtime_ms": 100},
        )
        assert output["status"] == "SUCCEEDED"

    def test_error_has_all_required_fields(self):
        from models.omnishotcut.adapter import OmniShotCutAdapter

        output = OmniShotCutAdapter._error(
            task_id="t1",
            video_id="v1",
            schema_version="1.0",
            code="TEST",
            message="test",
            retryable=False,
        )
        for field in self.SUCCESS_REQUIRED:
            assert field in output, f"Missing field: {field}"
        for field in self.ERROR_REQUIRED:
            assert field in output["error"], f"Missing error field: {field}"

    def test_error_empty_artifacts(self):
        from models.omnishotcut.adapter import OmniShotCutAdapter

        output = OmniShotCutAdapter._error(
            task_id="t1",
            video_id="v1",
            schema_version="1.0",
            code="TEST",
            message="test",
            retryable=False,
        )
        assert output["artifacts"] == {}

    def test_artifact_uri_format(self):
        from models.omnishotcut.adapter import OmniShotCutAdapter

        output = OmniShotCutAdapter._success(
            task_id="t1",
            video_id="v1",
            schema_version="1.0",
            artifact_key="shots",
            artifact_uri="storage://projects/p/v/video/artifacts/omnishotcut/0.1.0/shots.json",
            metrics={"shot_count": 1, "runtime_ms": 100},
        )
        assert output["artifacts"]["shots"].startswith("storage://")

    def test_no_forbidden_fields(self):
        import json

        from models.omnishotcut.adapter import OmniShotCutAdapter

        output = OmniShotCutAdapter._success(
            task_id="t1",
            video_id="v1",
            schema_version="1.0",
            artifact_key="shots",
            artifact_uri="storage://...",
            metrics={"shot_count": 1, "runtime_ms": 100},
        )
        raw = json.dumps(output)
        assert "action_score" not in raw
        assert "plot_score" not in raw

    def test_metrics_has_runtime(self):
        from models.omnishotcut.adapter import OmniShotCutAdapter

        output = OmniShotCutAdapter._success(
            task_id="t1",
            video_id="v1",
            schema_version="1.0",
            artifact_key="shots",
            artifact_uri="storage://...",
            metrics={"shot_count": 1, "runtime_ms": 12345},
        )
        assert "runtime_ms" in output["metrics"]
        assert output["metrics"]["runtime_ms"] == 12345
