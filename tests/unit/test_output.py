# tests/unit/test_output.py
import json
from io import StringIO
from pathlib import Path
from rich.console import Console
from setup_doctor.fixer import FixLogEntry, FixReport
from setup_doctor.output import print_fix_report, print_report, print_study_complete, render_text, render_json
from setup_doctor.engine import diagnose
from setup_doctor.models import CheckResult, CheckStatus, RemediationStep

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
    assert "nvm install 22" in text
    assert "root causes" in text
    assert "sdk" in text


def test_print_report_shows_terminal_sections():
    stream = StringIO()
    target = Console(file=stream, force_terminal=False, color_system=None, width=100)
    print_report(_report(), target)
    text = stream.getvalue()
    assert "SETUP DOCTOR" in text
    assert "HOW TO FIX" in text
    assert "ROOT CAUSES" in text
    assert "nvm install 22" in text


def test_fix_and_study_panels_show_completion_details():
    stream = StringIO()
    target = Console(file=stream, force_terminal=False, color_system=None, width=100)
    print_fix_report(FixReport("/repo/.setup-doctor-backup/run", [
        FixLogEntry("npm ci", "applied", operation="install-node-deps"),
    ]), target)
    print_study_complete("research/output/study_results.csv", target)
    text = stream.getvalue()
    assert "SAFE FIXES" in text
    assert "STUDY COMPLETE" in text
    assert "study_results.json" in text
