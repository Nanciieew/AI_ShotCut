"""
Environment detection — unified system / executable / PyTorch / storage checks.

All check functions return a flat dict with at minimum:
    {"check": str, "status": "PASS"|"WARNING"|"FAIL"|"NOT_INSTALLED"|"NOT_RUN",
     "value": Any, "detail": str|None}

Aggregate via EnvironmentReport in report.py.
"""

__version__ = "1.0.0"

from core.environment.report import EnvironmentReport, OverallStatus
from core.environment.system_info import collect_system_info
from core.environment.executable_info import collect_executable_info
from core.environment.pytorch_info import collect_pytorch_info
from core.environment.storage_info import collect_storage_info

__all__ = [
    "__version__",
    "EnvironmentReport",
    "OverallStatus",
    "collect_system_info",
    "collect_executable_info",
    "collect_pytorch_info",
    "collect_storage_info",
]
