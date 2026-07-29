"""
Environment report — aggregates all checks into a single structured report.

Usage:
    from core.environment.report import EnvironmentReport

    report = EnvironmentReport()
    report.add_system_info()
    report.add_executable_info()
    report.add_pytorch_info()
    report.add_storage_info()
    report.finalize()

    print(report.to_json())
    print(report.to_text())
"""

from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Optional

from core.environment import system_info, executable_info, pytorch_info, storage_info


class OverallStatus(str, Enum):
    READY = "READY"
    READY_WITH_WARNINGS = "READY_WITH_WARNINGS"
    BLOCKED = "BLOCKED"


class EnvironmentReport:
    """Collect and report environment health."""

    def __init__(self) -> None:
        self.checks: list[dict[str, Any]] = []
        self._overall: Optional[OverallStatus] = None
        self._generated_at: str = datetime.now(timezone.utc).isoformat()

    # ------------------------------------------------------------------
    # Collectors
    # ------------------------------------------------------------------

    def add_system_info(self) -> None:
        self.checks.extend(system_info.collect_system_info())

    def add_executable_info(self, storage_root: str | None = None) -> None:
        self.checks.extend(executable_info.collect_executable_info(storage_root))

    def add_pytorch_info(self) -> None:
        self.checks.extend(pytorch_info.collect_pytorch_info())

    def add_storage_info(
        self,
        storage_root: str | None = None,
        model_store_root: str | None = None,
    ) -> None:
        self.checks.extend(
            storage_info.collect_storage_info(storage_root, model_store_root)
        )

    def add_checks(self, checks: list[dict[str, Any]]) -> None:
        """Append arbitrary checks (e.g. from a model-specific script)."""
        self.checks.extend(checks)

    # ------------------------------------------------------------------
    # Finalize
    # ------------------------------------------------------------------

    def finalize(self) -> OverallStatus:
        """Compute overall status from all checks."""
        statuses = {c.get("status", "NOT_RUN") for c in self.checks}

        if "FAIL" in statuses:
            self._overall = OverallStatus.BLOCKED
        elif "WARNING" in statuses:
            self._overall = OverallStatus.READY_WITH_WARNINGS
        else:
            self._overall = OverallStatus.READY
        return self._overall

    @property
    def overall(self) -> Optional[OverallStatus]:
        return self._overall

    # ------------------------------------------------------------------
    # Serialization
    # ------------------------------------------------------------------

    def to_dict(self) -> dict[str, Any]:
        """Return a JSON-safe dict. Never includes secrets."""
        status = self._overall.value if self._overall else "NOT_FINALIZED"
        counts = self._count_statuses()

        return {
            "generated_at": self._generated_at,
            "overall_status": status,
            "summary": counts,
            "checks": self._sanitize_checks(),
        }

    def to_json(self, indent: int = 2) -> str:
        return json.dumps(self.to_dict(), indent=indent, ensure_ascii=False, default=str)

    # ------------------------------------------------------------------
    # Text report
    # ------------------------------------------------------------------

    def to_text(self) -> str:
        lines: list[str] = []
        width = 62

        lines.append("=" * width)
        lines.append("Environment Report — Movie Analysis Platform")
        lines.append("=" * width)
        lines.append(f"Generated: {self._generated_at}")
        status = self._overall.value if self._overall else "NOT_FINALIZED"
        icon = self._status_icon(status)
        lines.append(f"Overall:   {icon} {status}")
        lines.append("-" * width)

        # Grouped by check name prefix
        groups: dict[str, list[dict]] = {}
        for c in self.checks:
            prefix = c["check"].split("_")[0] if "_" in c["check"] else c["check"]
            groups.setdefault(prefix, []).append(c)

        for group, items in groups.items():
            lines.append(f"\n[{group}]")
            for c in items:
                icon = self._status_icon(c.get("status", "NOT_RUN"))
                val = c.get("value")
                detail = c.get("detail")
                line = f"  {icon} {c['check']}: {val}"
                if detail:
                    line += f"  ({detail})"
                lines.append(line)

        lines.append(f"\n{'=' * width}")
        counts = self._count_statuses()
        lines.append(f"PASS: {counts['PASS']}  WARNING: {counts['WARNING']}  "
                     f"FAIL: {counts['FAIL']}  NOT_INSTALLED: {counts['NOT_INSTALLED']}  "
                     f"NOT_RUN: {counts['NOT_RUN']}")

        if self._overall == OverallStatus.BLOCKED:
            lines.append("\n[BLOCKED] Fix FAIL items above before proceeding.")
        elif self._overall == OverallStatus.READY_WITH_WARNINGS:
            lines.append("\n[READY WITH WARNINGS] System is functional with caveats.")
        else:
            lines.append("\n[READY] All checks passed.")

        return "\n".join(lines)

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _status_icon(status: str) -> str:
        return {
            "PASS": "[OK]",
            "WARNING": "[WARN]",
            "FAIL": "[FAIL]",
            "NOT_INSTALLED": "[MISS]",
            "NOT_RUN": "[SKIP]",
        }.get(status, "[?]")

    def _count_statuses(self) -> dict[str, int]:
        counts: dict[str, int] = {"PASS": 0, "WARNING": 0, "FAIL": 0,
                                   "NOT_INSTALLED": 0, "NOT_RUN": 0}
        for c in self.checks:
            s = c.get("status", "NOT_RUN")
            counts[s] = counts.get(s, 0) + 1
        return counts

    def _sanitize_checks(self) -> list[dict[str, Any]]:
        """Remove any sensitive values from check output.

        Strips: passwords, full connection strings, API keys, tokens.
        """
        sensitive_keys = {"password", "secret", "api_key", "token", "dsn",
                          "connection_string", "database_url"}
        sanitized: list[dict[str, Any]] = []
        for c in self.checks:
            entry: dict[str, Any] = {}
            for k, v in c.items():
                if k.lower() in sensitive_keys:
                    entry[k] = "[REDACTED]"
                elif isinstance(v, str) and len(v) > 200:
                    # Long strings might contain connection strings
                    lower = v.lower()
                    if any(marker in lower for marker in
                           ("password=", "://", "secret=", "token=")):
                        entry[k] = "[REDACTED — possible credential]"
                    else:
                        entry[k] = v
                else:
                    entry[k] = v
            sanitized.append(entry)
        return sanitized
