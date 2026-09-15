# src/setup_doctor/engine.py
from __future__ import annotations
from datetime import datetime, timezone
from .models import Report, Diagnosis, RootCause, CheckResult, CheckStatus, Severity


def _build_summary(checks: list[CheckResult]) -> dict:
    return {
        "total": len(checks),
        "pass": sum(1 for c in checks if c.status == CheckStatus.PASS),
        "fail": sum(1 for c in checks if c.status == CheckStatus.FAIL),
        "skip": sum(1 for c in checks if c.status == CheckStatus.SKIP),
        "warnings": sum(1 for c in checks if c.status == CheckStatus.FAIL and c.severity == Severity.WARNING),
    }


def _compute_exit_code(checks: list[CheckResult]) -> int:
    if any(c.status == CheckStatus.FAIL and c.severity == Severity.ERROR for c in checks):
        return 1
    return 0


def diagnose(checks: list[CheckResult], mode: str, repo_path: str, os_name: str) -> Report:
    if mode == "dep":
        diagnosis = _build_dag_diagnosis(checks)
    else:
        diagnosis = None
    return Report(
        repo_path=repo_path,
        os=os_name,
        mode=mode,
        generated_at=datetime.now(timezone.utc).isoformat(),
        summary=_build_summary(checks),
        checks=checks,
        diagnosis=diagnosis,
        exit_code=_compute_exit_code(checks),
    )


def _build_dag_diagnosis(checks: list[CheckResult]) -> Diagnosis:
    """Placeholder — implemented in Task 12 (dep mode)."""
    return Diagnosis(root_causes=[])