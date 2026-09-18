# tests/unit/test_output.py
import json
from pathlib import Path
from setup_doctor.output import render_text, render_json
from setup_doctor.engine import diagnose
from setup_doctor.models import AIStatus, CheckResult, CheckStatus, RemediationStep

SNAP = Path(__file__).parent.parent / "snapshots" / "report_basic.json"


def _report():
    checks = [
        CheckResult("sdk", "SDK", "node", status=CheckStatus.FAIL,
                    evidence="node v18 expected >=20",
                    remediation=[RemediationStep("Install node 22", "nvm install 22", safe_fix=False)],
                    depends_on=["runtime"]),
        CheckResult("deps", "Deps", "node", status=CheckStatus.FAIL,
                    evidence="missing", depends_on=["sdk"]),
    ]
    return diagnose(checks, "dep", "/repo", "windows")


def test_render_json_matches_snapshot():
    data = json.loads(render_json(_report()))
    expected = json.loads(SNAP.read_text(encoding="utf-8"))
    # generated_at differs every run; compare everything else
    data.pop("generated_at")
    assert data == expected


def test_render_text_contains_fix_commands():
    text = render_text(_report())
    assert "[FAIL]" in text
    assert "AI: disabled (rule-based remediation only)" in text
    assert "nvm install 22" in text
    assert "root causes" in text
    assert "sdk" in text


def test_render_text_labels_ai_status_and_suggestions():
    report = _report()
    report.ai_status = AIStatus("enhanced", "openai", "gpt-4o-mini", 1)
    report.checks[0].remediation.append(RemediationStep("Upgrade node", "nvm install 20", source="ai"))
    text = render_text(report)
    assert "AI: enhanced (openai/gpt-4o-mini); 1 suggestion(s) added" in text
    assert "[RULE]" in text
    assert "[AI]" in text
