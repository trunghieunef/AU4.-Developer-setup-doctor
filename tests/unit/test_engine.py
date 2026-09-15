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


# ---------------- Dep mode (DAG) section ----------------
def test_dep_groups_root_cause():
    checks = [
        CheckResult("sdk", "SDK", "node", status=CheckStatus.FAIL, depends_on=[]),
        CheckResult("deps", "Deps", "node", status=CheckStatus.FAIL, depends_on=["sdk"]),
        CheckResult("build", "Build", "node", status=CheckStatus.FAIL, depends_on=["deps"]),
        CheckResult("lock", "Lock", "node", status=CheckStatus.PASS),
    ]
    report = diagnose(checks, "dep", "/repo", "windows")
    assert report.diagnosis is not None
    rcs = report.diagnosis.root_causes
    assert len(rcs) == 1
    assert rcs[0].cause_check_id == "sdk"
    assert set(rcs[0].affected_checks) == {"sdk", "deps", "build"}
    assert rcs[0].chain == "sdk → deps → build"
    assert checks[1].caused_by == "sdk"
    assert checks[1].causes == ["sdk"]
    assert checks[2].caused_by == "sdk"
    assert checks[0].caused_by is None


def test_dep_two_independent_roots():
    checks = [
        CheckResult("a", "A", "node", status=CheckStatus.FAIL, depends_on=[]),
        CheckResult("b", "B", "node", status=CheckStatus.FAIL, depends_on=[]),
    ]
    report = diagnose(checks, "dep", "/repo", "windows")
    assert len(report.diagnosis.root_causes) == 2


def test_dep_mixed_pass_fail_no_caused_by_on_pass():
    checks = [
        CheckResult("a", "A", "node", status=CheckStatus.FAIL, depends_on=[]),
        CheckResult("b", "B", "node", status=CheckStatus.PASS, depends_on=["a"]),
    ]
    report = diagnose(checks, "dep", "/repo", "windows")
    assert checks[1].caused_by is None
    assert len(report.diagnosis.root_causes) == 1


def test_dep_multiple_dependencies_fail_lists_all_roots():
    # node.deps.installed phụ thuộc cả lockfile + SDK; cả hai fail -> 2 root causes
    checks = [
        CheckResult("sdk", "SDK", "node", status=CheckStatus.FAIL, depends_on=[]),
        CheckResult("lock", "Lock", "node", status=CheckStatus.FAIL, depends_on=[]),
        CheckResult("deps", "Deps", "node", status=CheckStatus.FAIL,
                    depends_on=["lock", "sdk"]),
    ]
    report = diagnose(checks, "dep", "/repo", "windows")
    rc_ids = {rc.cause_check_id for rc in report.diagnosis.root_causes}
    assert rc_ids == {"sdk", "lock"}
    assert checks[2].caused_by == "lock"  # primary = root đầu tiên theo thứ tự ổn định
    assert set(checks[2].causes) == {"lock", "sdk"}
    # deps có mặt trong affected của CẢ HAI root causes
    for rc in report.diagnosis.root_causes:
        assert "deps" in rc.affected_checks


def test_dep_skip_dependency_bridges_to_root():
    # runtime SKIP (không fail) nhưng sdk phụ thuộc runtime và FAIL -> sdk là root cause
    checks = [
        CheckResult("runtime", "Runtime", "node", status=CheckStatus.SKIP),
        CheckResult("sdk", "SDK", "node", status=CheckStatus.FAIL, depends_on=["runtime"]),
    ]
    report = diagnose(checks, "dep", "/repo", "windows")
    assert len(report.diagnosis.root_causes) == 1
    assert report.diagnosis.root_causes[0].cause_check_id == "sdk"


def test_dep_cycle_does_not_loop():
    checks = [
        CheckResult("a", "A", "node", status=CheckStatus.FAIL, depends_on=["b"]),
        CheckResult("b", "B", "node", status=CheckStatus.FAIL, depends_on=["a"]),
    ]
    report = diagnose(checks, "dep", "/repo", "windows")
    ids = {rc.cause_check_id for rc in report.diagnosis.root_causes}
    assert ids  # non-empty
    assert len(report.diagnosis.root_causes) >= 1


def test_dep_depends_on_missing_id_is_ignored_safely():
    checks = [CheckResult("a", "A", "node", status=CheckStatus.FAIL,
                          depends_on=["does-not-exist"])]
    report = diagnose(checks, "dep", "/repo", "windows")
    assert len(report.diagnosis.root_causes) == 1
    assert report.diagnosis.root_causes[0].cause_check_id == "a"
    assert checks[0].caused_by is None