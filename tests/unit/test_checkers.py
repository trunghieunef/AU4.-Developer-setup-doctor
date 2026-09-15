# tests/unit/test_checkers.py  (node section)
from setup_doctor.checkers.node import NodeChecker
from setup_doctor.context import CheckContext
from setup_doctor.models import CheckStatus
from setup_doctor.utils.commands import CommandResult
from conftest import write_json


def _node_context(tmp_path, files):
    for rel, data in files.items():
        p = tmp_path / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(data, encoding="utf-8")
    return tmp_path


def _patch(fake_runner, monkeypatch, node_exe="C:\\node\\node.exe"):
    def _which(name):
        if name == "node":
            return node_exe
        if name == "npm":
            return "C:\\node\\npm.cmd"
        return None
    monkeypatch.setattr("setup_doctor.checkers.node.which", _which)
    monkeypatch.setattr("setup_doctor.checkers.node.run_command", fake_runner)
    return node_exe


def test_node_pass(fake_runner, monkeypatch, tmp_path):
    repo = _node_context(tmp_path, {
        "package.json": '{"engines": {"node": ">=18.0.0"}, "scripts": {"build": "tsc"}}',
        "package-lock.json": "{}",
    })
    (repo / "node_modules").mkdir()
    exe = _patch(fake_runner, monkeypatch)
    fake_runner.set([exe, "--version"], CommandResult(0, "v22.3.0", ""))
    results = NodeChecker().run(CheckContext(repo_path=str(repo), os="windows"))
    by_id = {r.check_id: r for r in results}
    assert by_id["node.runtime.present"].status == CheckStatus.PASS
    assert by_id["node.sdk.version"].status == CheckStatus.PASS
    assert by_id["node.lockfile.exists"].status == CheckStatus.PASS
    assert by_id["node.deps.installed"].status == CheckStatus.PASS


def test_node_fail_sdk_and_deps(fake_runner, monkeypatch, tmp_path):
    repo = _node_context(tmp_path, {
        "package.json": '{"engines": {"node": ">=20.0.0"}, "scripts": {"build": "tsc"}}',
        "package-lock.json": "{}",
    })
    exe = _patch(fake_runner, monkeypatch)
    fake_runner.set([exe, "--version"], CommandResult(0, "v18.16.0", ""))
    results = NodeChecker().run(CheckContext(repo_path=str(repo), os="windows"))
    by_id = {r.check_id: r for r in results}
    assert by_id["node.sdk.version"].status == CheckStatus.FAIL
    assert by_id["node.deps.installed"].status == CheckStatus.FAIL
    assert by_id["node.deps.installed"].remediation[0].command == "npm ci"


def test_node_runtime_version_fails_is_error(fake_runner, monkeypatch, tmp_path):
    repo = _node_context(tmp_path, {"package.json": "{}"})
    exe = _patch(fake_runner, monkeypatch)
    fake_runner.set([exe, "--version"], CommandResult(1, "", "error"))
    results = NodeChecker().run(CheckContext(repo_path=str(repo), os="windows"))
    by_id = {r.check_id: r for r in results}
    assert by_id["node.runtime.present"].status == CheckStatus.FAIL


def test_node_missing_npm_is_fail(fake_runner, monkeypatch, tmp_path):
    repo = _node_context(tmp_path, {"package.json": "{}"})
    exe = "C:\\node\\node.exe"
    monkeypatch.setattr("setup_doctor.checkers.node.which",
                        lambda name: exe if name == "node" else None)
    monkeypatch.setattr("setup_doctor.checkers.node.run_command", fake_runner)
    fake_runner.set([exe, "--version"], CommandResult(0, "v22.0.0", ""))
    results = NodeChecker().run(CheckContext(repo_path=str(repo), os="windows"))
    by_id = {r.check_id: r for r in results}
    assert by_id["node.pkgmgr.present"].status == CheckStatus.FAIL


# ---------------- Python section ----------------
from setup_doctor.checkers.python_ck import PythonChecker


def _python_patch(fake_runner, monkeypatch):
    monkeypatch.setattr("setup_doctor.checkers.python_ck.which",
                        lambda name: "C:\\Python\\py.exe" if name == "py" else None)
    monkeypatch.setattr("setup_doctor.checkers.python_ck.run_command", fake_runner)
    return "C:\\Python\\py.exe"


def test_python_pass(fake_runner, monkeypatch, tmp_path):
    repo = _node_context(tmp_path, {"pyproject.toml": '[project]\nrequires-python = ">=3.11"\n'})
    # .venv phải có pyvenv.cfg mới hợp lệ (#5)
    (repo / ".venv").mkdir()
    (repo / ".venv" / "pyvenv.cfg").write_text("home = C:\\Python\\3.12\n", encoding="utf-8")
    exe = _python_patch(fake_runner, monkeypatch)
    fake_runner.set([exe, "--version"], CommandResult(0, "Python 3.12.1", ""))
    results = PythonChecker().run(CheckContext(repo_path=str(repo), os="windows"))
    by_id = {r.check_id: r for r in results}
    assert by_id["python.runtime.present"].status == CheckStatus.PASS
    assert by_id["python.version"].status == CheckStatus.PASS
    assert by_id["python.env.present"].status == CheckStatus.PASS


def test_python_fail_version(fake_runner, monkeypatch, tmp_path):
    repo = _node_context(tmp_path, {"pyproject.toml": '[project]\nrequires-python = ">=3.11"\n'})
    (repo / ".venv").mkdir()
    (repo / ".venv" / "pyvenv.cfg").write_text("home = C:\\Python\\3.12\n", encoding="utf-8")
    exe = _python_patch(fake_runner, monkeypatch)
    fake_runner.set([exe, "--version"], CommandResult(0, "Python 3.9.5", ""))
    results = PythonChecker().run(CheckContext(repo_path=str(repo), os="windows"))
    assert {r.check_id for r in results if r.status == CheckStatus.FAIL} == {"python.version"}


def test_python_runtime_version_fails_is_error(fake_runner, monkeypatch, tmp_path):
    repo = _node_context(tmp_path, {"pyproject.toml": '[project]\nrequires-python = ">=3.11"\n'})
    exe = _python_patch(fake_runner, monkeypatch)
    fake_runner.set([exe, "--version"], CommandResult(1, "", "python: error"))
    results = PythonChecker().run(CheckContext(repo_path=str(repo), os="windows"))
    by_id = {r.check_id: r for r in results}
    assert by_id["python.runtime.present"].status == CheckStatus.FAIL


def test_python_deps_fail_when_venv_missing(fake_runner, monkeypatch, tmp_path):
    # Có requirements.txt nhưng không có .venv -> deps phải FAIL (không PASS vì không kiểm tra được)
    repo = _node_context(tmp_path, {
        "pyproject.toml": '[project]\nrequires-python = ">=3.11"\n',
        "requirements.txt": "requests==2.31.0\n",
    })
    exe = _python_patch(fake_runner, monkeypatch)
    fake_runner.set([exe, "--version"], CommandResult(0, "Python 3.12.1", ""))
    results = PythonChecker().run(CheckContext(repo_path=str(repo), os="windows"))
    by_id = {r.check_id: r for r in results}
    assert by_id["python.env.present"].status == CheckStatus.FAIL
    assert by_id["python.deps.installed"].status == CheckStatus.FAIL