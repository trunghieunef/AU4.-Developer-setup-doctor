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


def _failed_roots_of(by_id: dict[str, CheckResult], check_id: str,
                     failed_ids: set[str], visiting: set[str]) -> set[str]:
    """Trả về tập root causes (failed, không có failed dependency) mà check_id phụ thuộc (gián tiếp).

    - Bỏ qua depends_on trỏ tới ID không tồn tại (missing) một cách an toàn.
    - SKIP dependency không phải failed -> KHÔNG phải root cause; nhưng vẫn được
      "bắc cầu" qua để tìm root xa hơn nếu có.
    - Cycle: đánh dấu visiting để không lặp vô hạn; node trong cycle không có
      failed dep ngoài vòng -> self root.
    """
    if check_id in visiting:
        return {check_id}
    visiting = visiting | {check_id}
    node = by_id.get(check_id)
    if node is None:
        return set()
    roots: set[str] = set()
    for dep in node.depends_on:
        dep_node = by_id.get(dep)
        if dep_node is None:
            continue  # missing ID: bỏ qua an toàn
        if dep_node.status == CheckStatus.FAIL:
            dep_roots = _failed_roots_of(by_id, dep, failed_ids, visiting)
            roots |= dep_roots if dep_roots else {dep}
        elif dep_node.status == CheckStatus.SKIP:
            # bridge qua skip để tìm root xa hơn (vd runtime skip -> sdk fail)
            dep_roots = _failed_roots_of(by_id, dep, failed_ids, visiting)
            if dep_roots:
                roots |= dep_roots
    return roots


def _build_dag_diagnosis(checks: list[CheckResult]) -> Diagnosis:
    by_id = {c.check_id: c for c in checks}
    failed_ids = {c.check_id for c in checks if c.status == CheckStatus.FAIL}
    for c in checks:
        if c.check_id not in failed_ids:
            continue
        roots = _failed_roots_of(by_id, c.check_id, failed_ids, set())
        # Primary = root đầu tiên theo depends_on đã duyệt (thứ tự sorted cho ổn định)
        c.causes = sorted(roots) if roots else [c.check_id]
        # Nếu check là root của chính nó (không có failed dep) -> caused_by = None
        c.caused_by = None if c.check_id in c.causes else (c.causes[0] if c.causes else None)
    # Root causes = các failed check không bị gây bởi root khác
    root_ids = sorted(
        c.check_id for c in checks
        if c.check_id in failed_ids and c.check_id in c.causes
    )
    root_causes: list[RootCause] = []
    for root_id in root_ids:
        affected = sorted(
            c.check_id for c in checks
            if c.check_id in failed_ids and root_id in c.causes
        )
        chain_nodes = [root_id]
        current = root_id
        while True:
            nxt = next(
                (c.check_id for c in checks
                 if c.check_id in failed_ids and c.check_id != root_id
                 and current in c.depends_on and root_id in c.causes),
                None,
            )
            if nxt is None or nxt in chain_nodes:
                break
            chain_nodes.append(nxt)
            current = nxt
        root_causes.append(RootCause(
            cause_check_id=root_id,
            message=f"{by_id[root_id].name} is a root cause of {len(affected)} failing check(s)",
            affected_checks=[root_id] + [a for a in affected if a != root_id],
            chain=" → ".join(chain_nodes),
        ))
    return Diagnosis(root_causes=root_causes)