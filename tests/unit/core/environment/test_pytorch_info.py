"""Unit tests for pytorch_info — robust to missing PyTorch / CUDA."""

from core.environment.pytorch_info import collect_pytorch_info


def test_collect_pytorch_info_returns_list():
    results = collect_pytorch_info()
    assert isinstance(results, list)
    assert len(results) >= 7


def test_pytorch_installed_check():
    results = collect_pytorch_info()
    pt = next(c for c in results if c["check"] == "pytorch_installed")
    assert pt["status"] in ("PASS", "NOT_INSTALLED")
    assert isinstance(pt["value"], bool)


def test_no_gpu_does_not_fail_project():
    """GPU unavailable must be WARNING, not FAIL."""
    results = collect_pytorch_info()
    cuda = next(c for c in results if c["check"] == "cuda_available")
    assert cuda["status"] != "FAIL", "No GPU must not block the project"


def test_gpu_count_when_no_cuda():
    results = collect_pytorch_info()
    cuda = next(c for c in results if c["check"] == "cuda_available")
    gpu_count = next(c for c in results if c["check"] == "gpu_count")
    if not cuda["value"]:
        assert gpu_count["status"] in ("WARNING", "NOT_RUN")


def test_graceful_without_torch(monkeypatch):
    """Simulate PyTorch not installed."""
    import core.environment.pytorch_info as mod

    original_import = __builtins__["__import__"]

    def fake_import(name, *args, **kwargs):
        if name == "torch":
            raise ImportError("No module named 'torch'")
        return original_import(name, *args, **kwargs)

    monkeypatch.setattr("builtins.__import__", fake_import)
    # Need to reload the module to re-run the import guard
    import importlib

    importlib.reload(mod)
    results = collect_pytorch_info()
    pt = next(c for c in results if c["check"] == "pytorch_installed")
    assert pt["status"] == "NOT_INSTALLED"
    # Restore
    importlib.reload(mod)
