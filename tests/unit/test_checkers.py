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


# ---------------- Java section ----------------
from setup_doctor.checkers.java import JavaChecker
from setup_doctor.models import Severity


def _java_patch(fake_runner, monkeypatch):
    monkeypatch.setattr("setup_doctor.checkers.java.which",
                        lambda name: "C:\\java\\java.exe" if name == "java" else ("C:\\maven\\mvn.cmd" if name == "mvn" else None))
    monkeypatch.setattr("setup_doctor.checkers.java.run_command", fake_runner)
    monkeypatch.setattr("setup_doctor.checkers.java._m2_cache_exists", lambda home: True)
    return "C:\\java\\java.exe"


def test_java_pass(fake_runner, monkeypatch, tmp_path):
    repo = _node_context(tmp_path, {"pom.xml": "<project><properties><maven.compiler.release>17</maven.compiler.release></properties></project>"})
    exe = _java_patch(fake_runner, monkeypatch)
    fake_runner.set([exe, "-version"], CommandResult(0, "openjdk version \"17.0.9\" 2023-10-17", ""))
    results = JavaChecker().run(CheckContext(repo_path=str(repo), os="windows"))
    # cache có -> java.deps.cached là WARNING (pass nhưng severity warning)
    assert {r.check_id for r in results if r.status == CheckStatus.FAIL} == set()
    cached = next(r for r in results if r.check_id == "java.deps.cached")
    assert cached.severity == Severity.WARNING
    assert cached.status == CheckStatus.PASS


def test_java_fail_version(fake_runner, monkeypatch, tmp_path):
    repo = _node_context(tmp_path, {"pom.xml": "<project><properties><maven.compiler.release>21</maven.compiler.release></properties></project>"})
    exe = _java_patch(fake_runner, monkeypatch)
    fake_runner.set([exe, "-version"], CommandResult(0, 'openjdk version "11.0.20" 2023-07-18', ""))
    results = JavaChecker().run(CheckContext(repo_path=str(repo), os="windows"))
    assert {r.check_id for r in results if r.status == CheckStatus.FAIL} == {"java.version"}


def test_java_runtime_version_fails_is_error(fake_runner, monkeypatch, tmp_path):
    repo = _node_context(tmp_path, {"pom.xml": "<project/>"})
    exe = "C:\\java\\java.exe"
    monkeypatch.setattr("setup_doctor.checkers.java.which",
                        lambda name: exe if name == "java" else None)
    monkeypatch.setattr("setup_doctor.checkers.java.run_command", fake_runner)
    fake_runner.set([exe, "-version"], CommandResult(1, "", "error: invalid flag"))
    results = JavaChecker().run(CheckContext(repo_path=str(repo), os="windows"))
    by_id = {r.check_id: r for r in results}
    # runtime fail là gốc; downstream (maven/gradle, deps.cached) cũng fail theo
    assert by_id["java.runtime.present"].status == CheckStatus.FAIL
    assert by_id["java.version"].status == CheckStatus.SKIP  # bị skip vì runtime hỏng


# ---------------- .NET section ----------------
from setup_doctor.checkers.dotnet_ck import DotnetChecker


def _dotnet_patch(fake_runner, monkeypatch):
    monkeypatch.setattr("setup_doctor.checkers.dotnet_ck.which",
                        lambda name: "C:\\dotnet\\dotnet.exe" if name == "dotnet" else None)
    monkeypatch.setattr("setup_doctor.checkers.dotnet_ck.run_command", fake_runner)
    monkeypatch.setattr("setup_doctor.checkers.dotnet_ck._nuget_cache_ok", lambda: True)
    return "C:\\dotnet\\dotnet.exe"


def test_dotnet_pass(fake_runner, monkeypatch, tmp_path):
    repo = _node_context(tmp_path, {"global.json": '{"sdk": {"version": "8.0.100"}}', "App.csproj": "<Project Sdk=\"Microsoft.NET.Sdk\" />"})
    exe = _dotnet_patch(fake_runner, monkeypatch)
    fake_runner.set([exe, "--list-sdks"], CommandResult(0, "8.0.100 [C:\\dotnet\\sdk]", ""))
    results = DotnetChecker().run(CheckContext(repo_path=str(repo), os="windows"))
    assert {r.check_id for r in results if r.status == CheckStatus.FAIL} == set()
    # cache có -> restore.ready là warning (pass nhưng severity warning)
    ready = next(r for r in results if r.check_id == "dotnet.restore.ready")
    assert ready.severity == Severity.WARNING


def test_dotnet_fail_missing_sdk(fake_runner, monkeypatch, tmp_path):
    repo = _node_context(tmp_path, {"global.json": '{"sdk": {"version": "9.0.100"}}', "App.csproj": "<Project Sdk=\"Microsoft.NET.Sdk\" />"})
    exe = _dotnet_patch(fake_runner, monkeypatch)
    fake_runner.set([exe, "--list-sdks"], CommandResult(0, "8.0.100 [C:\\dotnet\\sdk]", ""))
    results = DotnetChecker().run(CheckContext(repo_path=str(repo), os="windows"))
    assert {r.check_id for r in results if r.status == CheckStatus.FAIL} == {"dotnet.sdk.version"}


def test_dotnet_cli_list_fails_is_error(fake_runner, monkeypatch, tmp_path):
    repo = _node_context(tmp_path, {"App.csproj": "<Project Sdk=\"Microsoft.NET.Sdk\" />"})
    exe = "C:\\dotnet\\dotnet.exe"
    monkeypatch.setattr("setup_doctor.checkers.dotnet_ck.which",
                        lambda name: exe if name == "dotnet" else None)
    monkeypatch.setattr("setup_doctor.checkers.dotnet_ck.run_command", fake_runner)
    fake_runner.set([exe, "--list-sdks"], CommandResult(1, "", "error"))
    results = DotnetChecker().run(CheckContext(repo_path=str(repo), os="windows"))
    by_id = {r.check_id: r for r in results}
    assert by_id["dotnet.runtime.present"].status == CheckStatus.FAIL
    assert by_id["dotnet.sdk.version"].status == CheckStatus.SKIP