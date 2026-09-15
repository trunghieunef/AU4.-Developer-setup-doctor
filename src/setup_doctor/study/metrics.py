# src/setup_doctor/study/metrics.py
from __future__ import annotations
from ..models import Report, CheckStatus


def compute_metrics(report: Report, ground_truth: dict) -> dict:
    """Tính metrics trên universe nhãn đã gán = expected_failures ∪ expected_passes.

    Quy tắc (chốt review #7):
    - Mọi ID trong ground truth THUỘC universe.
    - TP: tool fail & gt fail.
    - FP: tool fail & gt pass (tường minh).
    - FN: tool pass/skip, HOẶC tool không emit check đó (status None) — gt fail.
    - TN: tool pass & gt pass.
    - Tool fail cho ID KHÔNG có trong gt -> không tính FP (không phạt phát hiện thêm).
    """
    expected_fail = set(ground_truth.get("expected_failures", []))
    expected_pass = set(ground_truth.get("expected_passes", []))
    universe = expected_fail | expected_pass
    if not universe:
        return {
            "total": 0, "universe": 0, "tp": 0, "fp": 0, "fn": 0, "tn": 0,
            "precision": 0.0, "recall": 0.0, "f1": 0.0, "accuracy": 0.0,
            "clarity": 0.0, "predicted": [], "expected": sorted(expected_fail),
        }
    status_by_id = {c.check_id: c.status for c in report.checks}

    tp = fp = fn = tn = 0
    for check_id in universe:
        status = status_by_id.get(check_id)  # None nếu tool không emit check -> FN
        is_fail = status == CheckStatus.FAIL
        if check_id in expected_fail:
            if is_fail:
                tp += 1
            else:
                fn += 1
        else:  # expected pass
            if is_fail:
                fp += 1
            else:
                tn += 1

    precision = tp / (tp + fp) if (tp + fp) else 0.0
    recall = tp / (tp + fn) if (tp + fn) else 0.0
    f1 = 2 * precision * recall / (precision + recall) if (precision + recall) else 0.0
    accuracy = (tp + tn) / len(universe) if universe else 0.0

    clarity = 0.0
    if report.diagnosis is not None:
        expected_rc = set(ground_truth.get("expected_root_causes", []))
        rc_ids = {rc.cause_check_id for rc in report.diagnosis.root_causes}
        clarity = len(rc_ids & expected_rc) / len(expected_rc) if expected_rc else 0.0

    return {
        "total": len(report.checks), "universe": len(universe),
        "tp": tp, "fp": fp, "fn": fn, "tn": tn,
        "precision": round(precision, 4), "recall": round(recall, 4),
        "f1": round(f1, 4), "accuracy": round(accuracy, 4),
        "clarity": round(clarity, 4),
        "predicted": sorted(check_id for check_id, st in status_by_id.items() if st == CheckStatus.FAIL),
        "expected": sorted(expected_fail),
    }