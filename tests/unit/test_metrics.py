# tests/unit/test_metrics.py
import pytest
from setup_doctor.study.metrics import compute_metrics
from setup_doctor.models import Report, CheckResult, CheckStatus, Diagnosis, RootCause


def _report(mode="flat"):
    checks = [
        CheckResult("a", "A", "node", status=CheckStatus.FAIL),
        CheckResult("b", "B", "node", status=CheckStatus.FAIL),
        CheckResult("c", "C", "node", status=CheckStatus.PASS),
    ]
    return Report(repo_path="/r", os="windows", mode=mode, summary={}, checks=checks,
                  diagnosis=Diagnosis(root_causes=[RootCause("a", "m", ["a", "b"], "a → b")]) if mode == "dep" else None)


def test_metrics_precision_recall_accuracy():
    gt = {"expected_failures": ["a", "b"], "expected_passes": ["c"]}
    m = compute_metrics(_report(), gt)
    assert m["tp"] == 2
    assert m["fp"] == 0
    assert m["fn"] == 0
    assert m["tn"] == 1
    assert m["precision"] == 1.0
    assert m["recall"] == 1.0
    assert m["f1"] == 1.0
    assert m["accuracy"] == 1.0  # (2+1)/3 universe


def test_metrics_recall_partial():
    # "zz" nằm trong expected_failures -> THUỘC universe. Tool không emit check "zz"
    # -> FN=1 (theo quy tắc 4.6, ID trong GT luôn thuộc universe; không emit = FN).
    gt = {"expected_failures": ["a", "b", "zz"], "expected_passes": ["c"]}
    m = compute_metrics(_report(), gt)
    assert m["recall"] == pytest.approx(2 / 3, abs=1e-3)
    assert m["fn"] == 1
    assert m["accuracy"] == pytest.approx(3 / 4, abs=1e-3)  # (tp=2 + tn=1) / universe(4)


def test_metrics_missing_emit_is_fn():
    # ground truth gán fail cho check KHÔNG có trong report -> FN (tool không emit)
    gt = {"expected_failures": ["a", "zz"], "expected_passes": []}
    m = compute_metrics(_report(), gt)
    assert m["fn"] == 1  # zz không emit -> FN


def test_metrics_fp_only_when_gt_explicitly_passes():
    # Tool báo fail cho check "d" (KHÔNG có trong ground truth) -> không tính FP
    # (check chưa được gán nhãn, không phạt tool vì phát hiện thêm).
    checks = _report().checks + [CheckResult("d", "D", "node", status=CheckStatus.FAIL)]
    report = Report(repo_path="/r", os="windows", mode="flat", summary={}, checks=checks)
    gt = {"expected_failures": ["a", "b"], "expected_passes": ["c"]}
    m = compute_metrics(report, gt)
    assert m["fp"] == 0
    assert m["precision"] == 1.0


def test_metrics_fp_when_gt_passes_but_tool_fails():
    checks = [CheckResult("a", "A", "node", status=CheckStatus.FAIL)]
    report = Report(repo_path="/r", os="windows", mode="flat", summary={}, checks=checks)
    gt = {"expected_failures": [], "expected_passes": ["a"]}
    m = compute_metrics(report, gt)
    assert m["fp"] == 1
    assert m["precision"] == 0.0


def test_validate_ground_truth_rejects_unknown_ids():
    # ID trong ground truth phải thuộc catalog check; sai -> reject (#7)
    from setup_doctor.study.ground_truth import validate_ground_truth
    catalog_ids = {"a", "b", "c", "node.sdk.version"}
    bad = {"expected_failures": ["a", "node.sdk.version", "zz-not-a-check"]}
    errors = validate_ground_truth(bad, catalog_ids)
    assert len(errors) == 1
    assert "zz-not-a-check" in errors[0]


def test_metrics_clarity_dep_mode():
    gt = {"expected_failures": ["a", "b"], "expected_root_causes": ["a"]}
    m = compute_metrics(_report(mode="dep"), gt)
    assert m["clarity"] == 1.0


def test_metrics_clarity_zero_when_none_expected():
    gt = {"expected_failures": ["a", "b"], "expected_root_causes": []}
    m = compute_metrics(_report(mode="dep"), gt)
    assert m["clarity"] == 0.0