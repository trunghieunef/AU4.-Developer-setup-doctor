# src/setup_doctor/output.py
from __future__ import annotations
import json
from .models import Report, CheckStatus


def render_text(report: Report) -> str:
    lines = [f"setup-doctor report (mode: {report.mode})",
             f"repo: {report.repo_path} | os: {report.os}",
             f"summary: {report.summary}"]
    marks = {
        CheckStatus.PASS: "[PASS]", CheckStatus.FAIL: "[FAIL]", CheckStatus.SKIP: "[SKIP]",
    }
    for c in report.checks:
        lines.append(f"{marks[c.status]} {c.check_id}: {c.evidence}")
        if c.status == CheckStatus.FAIL:
            for i, r in enumerate(c.remediation, 1):
                lines.append(f"    fix {i}: {r.step} -> {r.command}")
    if report.diagnosis and report.diagnosis.root_causes:
        lines.append("root causes:")
        for rc in report.diagnosis.root_causes:
            lines.append(f"  - {rc.cause_check_id}: {rc.message} (chain: {rc.chain})")
    lines.append(f"exit_code: {report.exit_code}")
    return "\n".join(lines)


def render_json(report: Report) -> str:
    return json.dumps(report.to_dict(), indent=2, ensure_ascii=False)