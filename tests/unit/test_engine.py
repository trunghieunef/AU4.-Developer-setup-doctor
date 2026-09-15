# tests/unit/test_engine.py
from setup_doctor.engine import diagnose
from setup_doctor.models import CheckResult, CheckStatus, Severity


def _checks():
    return [
        CheckResult("a", "A", "node", status=CheckStatus.PASS),
        CheckResult("b", "B", "node", status=CheckStatus.FAIL, severity=Severity.ERROR),
        CheckResult("c", "C", "node", status=CheckStatus.SKIP),
    ]


def test_flat_report_has_no_diagnosis():
    report = diagnose(_checks(), "flat", "/repo", "windows")
    assert report.mode == "flat"
    assert report.diagnosis is None
    assert report.summary["total"] == 3
    assert report.summary["pass"] == 1
    assert report.summary["fail"] == 1
    assert report.summary["skip"] == 1


def test_exit_code_1_when_error_fail():
    report = diagnose(_checks(), "flat", "/repo", "windows")
    assert report.exit_code == 1


def test_exit_code_0_when_all_pass():
    checks = [CheckResult("a", "A", "node", status=CheckStatus.PASS)]
    report = diagnose(checks, "flat", "/repo", "windows")
    assert report.exit_code == 0


def test_warning_fail_does_not_set_exit_1():
    checks = [CheckResult("w", "W", "node", status=CheckStatus.FAIL, severity=Severity.WARNING)]
    report = diagnose(checks, "flat", "/repo", "windows")
    assert report.exit_code == 0
    assert report.summary["warnings"] == 1