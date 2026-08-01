"""Unit tests for EnvironmentReport — aggregation, sanitization, serialization."""

import json

from core.environment.report import EnvironmentReport, OverallStatus


def test_report_init():
    report = EnvironmentReport()
    assert report.checks == []
    assert report.overall is None


def test_report_add_system_info():
    report = EnvironmentReport()
    report.add_system_info()
    assert len(report.checks) > 0


def test_report_finalize_ready():
    report = EnvironmentReport()
    report.checks = [{"check": "test", "status": "PASS", "value": True, "detail": None}]
    status = report.finalize()
    assert status == OverallStatus.READY


def test_report_finalize_warning():
    report = EnvironmentReport()
    report.checks = [
        {"check": "a", "status": "PASS", "value": True, "detail": None},
        {"check": "b", "status": "WARNING", "value": None, "detail": "thing missing"},
    ]
    status = report.finalize()
    assert status == OverallStatus.READY_WITH_WARNINGS


def test_report_finalize_blocked():
    report = EnvironmentReport()
    report.checks = [
        {"check": "a", "status": "PASS", "value": True, "detail": None},
        {"check": "b", "status": "FAIL", "value": False, "detail": "disk full"},
    ]
    status = report.finalize()
    assert status == OverallStatus.BLOCKED


def test_report_to_dict():
    report = EnvironmentReport()
    report.add_system_info()
    report.finalize()
    d = report.to_dict()
    assert "generated_at" in d
    assert d["overall_status"] in ("READY", "READY_WITH_WARNINGS", "BLOCKED")
    assert "summary" in d
    assert "checks" in d


def test_report_to_json():
    report = EnvironmentReport()
    report.add_system_info()
    report.finalize()
    j = report.to_json()
    assert isinstance(j, str)
    parsed = json.loads(j)
    assert "overall_status" in parsed


def test_report_to_text():
    report = EnvironmentReport()
    report.add_system_info()
    report.finalize()
    t = report.to_text()
    assert "Environment Report" in t
    assert "Overall:" in t


def test_sanitize_removes_secrets():
    report = EnvironmentReport()
    report.checks = [
        {"check": "db", "status": "PASS", "value": True, "detail": None},
        {"check": "secret", "status": "PASS", "password": "abc123", "detail": "should be redacted"},
    ]
    report.finalize()
    d = report.to_dict()
    for c in d["checks"]:
        for k, v in c.items():
            if "password" in k.lower():
                assert v == "[REDACTED]"


def test_sanitize_long_connection_string():
    report = EnvironmentReport()
    report.checks = [
        {
            "check": "db",
            "status": "PASS",
            "value": "postgresql://user:password@host:5432/db?sslmode=require" * 5,
            "detail": None,
        },
    ]
    report.finalize()
    d = report.to_dict()
    val = d["checks"][0].get("value", "")
    assert "REDACTED" in val or "://" not in val


def test_storage_not_writable_simulated(tmp_path):
    """Simulate a non-writable storage directory."""
    report = EnvironmentReport()
    report.add_storage_info(storage_root=str(tmp_path / "nonexistent_new"))
    # Should auto-create and pass, or fail gracefully
    report.finalize()
    assert report.overall is not None


def test_no_gpu_is_not_project_fail():
    """When GPU is unavailable, overall must not be BLOCKED."""
    report = EnvironmentReport()
    report.checks = [
        {"check": "cuda_available", "status": "WARNING", "value": False, "detail": "CPU only"},
        {"check": "gpu_count", "status": "WARNING", "value": 0, "detail": "No GPU"},
    ]
    status = report.finalize()
    assert status != OverallStatus.BLOCKED
    assert status == OverallStatus.READY_WITH_WARNINGS
