# tests/integration/test_cli.py
import json
import subprocess
import sys
from conftest import write_json


def _run_cli(args):
    return subprocess.run(
        [sys.executable, "-m", "setup_doctor.cli", *args],
        capture_output=True, text=True,
    )


def test_cli_version():
    res = _run_cli(["--version"])
    assert res.returncode == 0
    assert "setup-doctor" in res.stdout


def test_cli_check_no_ecosystem_exit_0(tmp_path):
    res = _run_cli(["check", str(tmp_path), "--format", "json"])
    assert res.returncode == 0
    assert "no supported ecosystem" in res.stdout
    # Output vẫn là JSON hợp lệ (machine-readable không bị phá vỡ)
    _json = json
    data = _json.loads(res.stdout)
    assert data["exit_code"] == 0


def test_cli_check_missing_path_exit_2(tmp_path):
    res = _run_cli(["check", str(tmp_path / "does-not-exist"), "--format", "json"])
    assert res.returncode == 2  # path không tồn tại -> lỗi input, KHÔNG phải no-ecosystem
    assert "invalid repo path" in res.stderr or "does not exist" in res.stderr


def test_cli_check_json_ok(fake_runner, monkeypatch, tmp_path):
    write_json(tmp_path / "package.json", {"engines": {"node": ">=18.0.0"}})
    (tmp_path / "package-lock.json").write_text("{}", encoding="utf-8")
    (tmp_path / "node_modules").mkdir()
    exe = "C:\\node\\node.exe"
    fake_runner.set([exe, "--version"], _cmd_result(0, "v22.0.0", ""))
    monkeypatch.setattr("setup_doctor.checkers.node.which",
                        lambda name: exe if name == "node" else (r"C:\node\npm.cmd" if name == "npm" else None))
    monkeypatch.setattr("setup_doctor.checkers.node.run_command", fake_runner)
    # -m setup_doctor.cli runs in a subprocess, so monkeypatch won't apply;
    # instead, invoke main() in-process for the node scenario.
    from setup_doctor.cli import main
    rc = main(["check", str(tmp_path), "--format", "json"])
    assert rc == 0


def _cmd_result(rc, stdout, stderr):
    from setup_doctor.utils.commands import CommandResult
    return CommandResult(rc, stdout, stderr)