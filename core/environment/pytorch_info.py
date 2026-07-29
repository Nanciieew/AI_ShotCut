"""
PyTorch / CUDA / GPU detection.

Gracefully degrades when PyTorch is not installed — never raises.
"""

import sys
from typing import Any


def collect_pytorch_info() -> list[dict[str, Any]]:
    """Check PyTorch installation, CUDA availability, GPU count/names.

    All failures are recorded as status values — no exceptions propagate.
    """
    results: list[dict[str, Any]] = []

    # ------------------------------------------------------------------
    # PyTorch import
    # ------------------------------------------------------------------
    torch_available = False
    try:
        import torch
        torch_available = True
    except ImportError:
        pass

    if not torch_available:
        results.append({"check": "pytorch_installed", "status": "NOT_INSTALLED", "value": False, "detail": "pip install torch"})
        for key in ("pytorch_version", "torchvision_version", "torch_cuda_version",
                     "cuda_available", "gpu_count", "gpu_names"):
            results.append({"check": key, "status": "NOT_RUN", "value": None, "detail": "PyTorch not installed"})
        return results

    import torch

    # --- PyTorch version ---
    results.append({
        "check": "pytorch_installed",
        "status": "PASS",
        "value": True,
        "detail": None,
    })
    results.append({
        "check": "pytorch_version",
        "status": "PASS",
        "value": torch.__version__,
        "detail": f"Install path: {getattr(torch, '__file__', 'unknown')}",
    })

    # --- Torchvision ---
    try:
        import torchvision
        tv_ver = torchvision.__version__
        results.append({
            "check": "torchvision_version",
            "status": "PASS",
            "value": tv_ver,
            "detail": None,
        })
    except ImportError:
        results.append({
            "check": "torchvision_version",
            "status": "NOT_INSTALLED",
            "value": None,
            "detail": "pip install torchvision",
        })

    # --- CUDA version string ---
    cuda_ver = getattr(torch.version, "cuda", None)
    results.append({
        "check": "torch_cuda_version",
        "status": "PASS" if cuda_ver else "WARNING",
        "value": cuda_ver,
        "detail": "CUDA toolkit version embedded in PyTorch build",
    })

    # --- CUDA available ---
    cuda_ok = torch.cuda.is_available()
    results.append({
        "check": "cuda_available",
        "status": "PASS" if cuda_ok else "WARNING",
        "value": cuda_ok,
        "detail": None if cuda_ok else "GPU acceleration unavailable — CPU-only mode",
    })

    # --- GPU count & names ---
    if cuda_ok:
        gpu_count = torch.cuda.device_count()
        gpu_names = [torch.cuda.get_device_name(i) for i in range(gpu_count)]
        results.append({
            "check": "gpu_count",
            "status": "PASS",
            "value": gpu_count,
            "detail": None,
        })
        results.append({
            "check": "gpu_names",
            "status": "PASS",
            "value": gpu_names,
            "detail": None,
        })
    else:
        results.append({
            "check": "gpu_count",
            "status": "WARNING",
            "value": 0,
            "detail": "No CUDA-capable GPU detected",
        })
        results.append({
            "check": "gpu_names",
            "status": "NOT_RUN",
            "value": [],
            "detail": "Skipped — CUDA not available",
        })

    return results
