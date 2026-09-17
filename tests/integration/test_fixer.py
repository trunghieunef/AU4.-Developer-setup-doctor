# tests/integration/test_fixer.py
import os
import pytest
from setup_doctor.fixer import Fixer
from setup_doctor.models import Report, CheckResult, CheckStatus, RemediationStep
from setup_doctor.utils.commands import CommandResult


def _step(op, disp, argv, safe=True, files=(), reversible=True):
    return RemediationStep(disp, disp, safe_fix=safe, files=list(files),
                           operation=op, argv=list(argv))


def _report_with_fixables():
    checks = [
        CheckResult("env", "env", "services", status=CheckStatus.FAIL,
                    remediation=[_step("create-env", "Create .env", [],
                                       files=[".env.example", ".env"], reversible=True)]),
        CheckResult("deps", "deps", "node", status=CheckStatus.FAIL,
                    remediation=[_step("install-node-deps", "npm ci", ["npm", "ci"],
                                       reversible=False)]),
        CheckResult("sdk", "sdk", "node", status=CheckStatus.FAIL,
                    remediation=[_step("set-sdk", "nvm install 22", ["nvm", "install", "22"],
                                       safe=False)]),  # not safe
    ]
    return Report(repo_path="", os="windows", summary={}, checks=checks)


def test_fixer_applies_safe_manual_and_backs_up(fake_runner, monkeypatch, tmp_path):
    (tmp_path / ".env.example").write_text("KEY=value\n", encoding="utf-8")
    (tmp_path / ".env").write_text("OLD=1\n", encoding="utf-8")
    fake_runner.set(["npm", "ci"], CommandResult(0, "", ""))
    monkeypatch.setattr("setup_doctor.fixer.run_command", fake_runner)

    report = _report_with_fixables()
    report.repo_path = str(tmp_path)
    fix = Fixer(str(tmp_path)).apply(report)

    statuses = {e.status for e in fix.entries}
    assert "applied" in statuses          # create-env + npm ci
    assert "skipped" in statuses          # nvm (not safe)
    assert (tmp_path / ".env").read_text(encoding="utf-8") == "KEY=value\n"
    backup_dir = os.path.join(str(tmp_path), ".setup-doctor-backup")
    assert os.path.isdir(backup_dir)
    backups = [d for d in os.listdir(backup_dir)]
    assert len(backups) == 1


def test_fixer_rolls_back_reversible_step_on_later_failure(fake_runner, monkeypatch, tmp_path):
    (tmp_path / ".env.example").write_text("KEY=value\n", encoding="utf-8")
    (tmp_path / ".env").write_text("OLD=1\n", encoding="utf-8")
    fake_runner.set(["npm", "ci"], CommandResult(1, "", "boom"))
    monkeypatch.setattr("setup_doctor.fixer.run_command", fake_runner)

    report = _report_with_fixables()
    report.checks = [c for c in report.checks if c.check_id in ("env", "deps")]
    report.repo_path = str(tmp_path)
    fix = Fixer(str(tmp_path)).apply(report)

    failed = next(e for e in fix.entries if e.status == "failed")
    assert failed.operation == "install-node-deps"
    assert "non-reversible" in failed.detail.lower() or "cannot rollback" in failed.detail.lower()
    rolled = next(e for e in fix.entries if e.status == "rolled_back")
    assert rolled.operation == "create-env"
    assert (tmp_path / ".env").read_text(encoding="utf-8") == "OLD=1\n"  # restored


def test_fixer_removes_newly_created_file_on_rollback(fake_runner, monkeypatch, tmp_path):
    (tmp_path / ".env.example").write_text("KEY=value\n", encoding="utf-8")
    fake_runner.set(["npm", "ci"], CommandResult(1, "", "boom"))
    monkeypatch.setattr("setup_doctor.fixer.run_command", fake_runner)

    report = _report_with_fixables()
    report.checks = [c for c in report.checks if c.check_id in ("env", "deps")]
    report.repo_path = str(tmp_path)
    Fixer(str(tmp_path)).apply(report)

    assert not (tmp_path / ".env").exists()  # file mới tạo (không có backup) bị xóa khi rollback


def test_fixer_rejects_unknown_operation(fake_runner, monkeypatch, tmp_path):
    bad = [CheckResult("x", "x", "node", status=CheckStatus.FAIL,
                       remediation=[_step("unknown-op", "a && b", ["a", "&&", "b"],
                                          reversible=False)])]
    report = Report(repo_path=str(tmp_path), os="windows", summary={}, checks=bad)
    fix = Fixer(str(tmp_path)).apply(report)
    assert fix.entries[0].status == "skipped"
    assert "not allowed" in fix.entries[0].detail


def test_fixer_uses_whitelisted_argv_not_step_argv(fake_runner, monkeypatch, tmp_path):
    monkeypatch.setattr("setup_doctor.fixer.run_command", fake_runner)
    report = Report(repo_path=str(tmp_path), os="windows", summary={}, checks=[
        CheckResult("deps", "deps", "node", status=CheckStatus.FAIL,
                    remediation=[_step("install-node-deps", "npm ci", ["evil-command"], reversible=False)]),
    ])
    fake_runner.set(["npm", "ci"], CommandResult(0, "", ""))
    fix = Fixer(str(tmp_path)).apply(report)
    assert fix.entries[0].status == "applied"
    assert fake_runner.calls == [["npm", "ci"]]


def test_fixer_rejects_path_outside_repo(fake_runner, monkeypatch, tmp_path):
    outside = [CheckResult("x", "x", "services", status=CheckStatus.FAIL,
                           remediation=[_step("create-env", "Create .env", [],
                                              files=["../outside.env", ".env"])])]
    report = Report(repo_path=str(tmp_path), os="windows", summary={}, checks=outside)
    fix = Fixer(str(tmp_path)).apply(report)
    assert fix.entries[0].status == "skipped"
    assert "outside repo" in fix.entries[0].detail.lower() or "path" in fix.entries[0].detail.lower()
