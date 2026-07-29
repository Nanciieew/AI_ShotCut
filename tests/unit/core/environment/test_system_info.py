"""Unit tests for system_info — CPU, OS, memory without side effects."""

import platform
import pytest

from core.environment.system_info import collect_system_info


def test_collect_system_info_returns_list():
    results = collect_system_info()
    assert isinstance(results, list)
    assert len(results) >= 8  # at minimum OS, arch, python, venv, cpu_model, cores×2, memory×2, psutil


def test_os_check_exists():
    results = collect_system_info()
    os_check = next(c for c in results if c["check"] == "operating_system")
    assert os_check["status"] == "PASS"
    assert os_check["value"] in ("Windows", "Linux", "Darwin")


def test_architecture_check():
    results = collect_system_info()
    arch = next(c for c in results if c["check"] == "architecture")
    assert arch["status"] == "PASS"
    assert arch["value"]


def test_python_version_check():
    results = collect_system_info()
    py = next(c for c in results if c["check"] == "python_version")
    assert py["status"] in ("PASS", "FAIL")
    assert py["value"]


def test_cpu_model_never_fails():
    """CPU model detection must return WARNING, never FAIL."""
    results = collect_system_info()
    cpu = next(c for c in results if c["check"] == "cpu_model")
    assert cpu["status"] in ("PASS", "WARNING"), f"cpu_model status={cpu['status']}"
    assert cpu["status"] != "FAIL", "CPU model failure must not block the project"


def test_cpu_cores():
    results = collect_system_info()
    phys = next(c for c in results if c["check"] == "cpu_physical_cores")
    logical = next(c for c in results if c["check"] == "cpu_logical_cores")
    # Either value may be None but status must not be FAIL
    assert phys["status"] != "FAIL"
    assert logical["status"] != "FAIL"


def test_psutil_check():
    results = collect_system_info()
    psutil_check = next(c for c in results if c["check"] == "psutil_available")
    assert psutil_check["status"] in ("PASS", "WARNING")
    assert isinstance(psutil_check["value"], bool)


def test_memory_check_exists():
    results = collect_system_info()
    mem = next(c for c in results if c["check"] == "total_memory_gb")
    assert mem["status"] != "FAIL"
