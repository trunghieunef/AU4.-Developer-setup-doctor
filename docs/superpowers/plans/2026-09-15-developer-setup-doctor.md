# Developer Setup Doctor Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build `setup-doctor`, a Python CLI that diagnoses one repository's SDK, dependencies, and local-service prerequisites, prints exact remediation steps, emits machine-readable JSON + exit codes, compares flat vs dependency-aware diagnosis modes, and runs a repeatable research harness — with optional AI-enhanced remediation/explanation that stays isolated from research.

**Architecture:** Plugin-style checker framework in Python 3.11+. Each ecosystem (node, python, java, dotnet, services, registry) is one read-only `Checker` class returning normalized `CheckResult` objects. A `DiagnosisEngine` consumes the same check results in two modes: `flat` (plain checklist) and `dep` (builds a DAG from `depends_on`, groups failures by root cause). Output layer renders text/JSON and computes exit codes. A `Fixer` applies only whitelisted `safe_fix` remediations with file backup + log + rollback. AI is an optional enhancement layer (`--ai`) with a provider interface and always-available rule-based fallback; the `study` harness is strictly rule-based/deterministic.

**Tech Stack:** Python ≥3.11, stdlib only for core (`argparse`, `tomllib`, `dataclasses`, `subprocess`, `socket`), `pytest` for tests, optional `openai`/`anthropic` for AI, `setuptools` packaging with `pyproject.toml`.

**Spec:** `docs/superpowers/specs/2026-09-15-developer-setup-doctor-design.md` (v1.1)

---

## File Structure (mapped before tasks)

```
pyproject.toml                     # packaging, console script, pytest config
src/setup_doctor/__init__.py       # __version__
src/setup_doctor/models.py         # CheckResult, RemediationStep, Report, Diagnosis, RootCause, enums
src/setup_doctor/context.py        # CheckContext
src/setup_doctor/config.py         # ToolConfig, AIConfig, load_config (file > env > CLI)
src/setup_doctor/registry.py       # detect_ecosystems, get_checkers, ALL_CHECKERS
src/setup_doctor/engine.py         # diagnose(), summary, exit code, DAG root-cause grouping
src/setup_doctor/output.py         # render_text, render_json
src/setup_doctor/fixer.py          # Fixer: backup dir, apply safe fixes, rollback, FixReport
src/setup_doctor/runner.py         # run_check orchestration, NoEcosystemError, AI hook
src/setup_doctor/checkers/base.py       # abstract Checker
src/setup_doctor/checkers/node.py       # 6 checks
src/setup_doctor/checkers/python_ck.py  # 5 checks
src/setup_doctor/checkers/java.py       # 5 checks
src/setup_doctor/checkers/dotnet_ck.py  # 4 checks
src/setup_doctor/checkers/services.py   # 5 checks
src/setup_doctor/checkers/registry.py   # 4 checks
src/setup_doctor/utils/commands.py      # run_command, CommandResult, which
src/setup_doctor/utils/versions.py      # parse_version, satisfies
src/setup_doctor/utils/osdetect.py      # detect_os
src/setup_doctor/ai/provider.py         # AIProvider protocol, OpenAI/Anthropic clients, get_provider
src/setup_doctor/ai/remediation.py      # AIRemediation
src/setup_doctor/ai/explainer.py        # AIExplainer
src/setup_doctor/study/metrics.py       # compute_metrics
src/setup_doctor/study/runner.py        # run_study
src/setup_doctor/cli.py                 # argparse main()
tests/conftest.py                       # FakeRunner + patch helpers, fixture seed builders
tests/unit/test_models.py
tests/unit/test_utils.py
tests/unit/test_config.py
tests/unit/test_registry.py
tests/unit/test_checkers.py
tests/unit/test_engine.py
tests/unit/test_output.py
tests/unit/test_ai.py
tests/unit/test_metrics.py
tests/integration/test_fixer.py
tests/integration/test_cli.py
tests/snapshots/report_basic.json      # golden JSON for snapshot test
```

---

## Task 1: Project skeleton (pyproject + package + models)

**Files:**
- Create: `pyproject.toml`
- Create: `src/setup_doctor/__init__.py`
- Create: `src/setup_doctor/models.py`
- Create: `tests/unit/test_models.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/unit/test_models.py
from setup_doctor.models import (
    CheckResult, RemediationStep, Report, Diagnosis, RootCause,
    CheckStatus, Severity,
)

def test_check_result_to_dict_uses_enum_values():
    cr = CheckResult(
        check_id="node.sdk.version",
        name="Node.js SDK version",
        ecosystem="node",
        severity=Severity.ERROR,
        status=CheckStatus.FAIL,
        evidence="Node v18.16.0 found",
        remediation=[RemediationStep("Install Node 22", "nvm install 22", safe_fix=True)],
        depends_on=["node.runtime.present"],
    )
    d = cr.to_dict()
    assert d["check_id"] == "node.sdk.version"
    assert d["severity"] == "error"          # enum value, not enum object
    assert d["status"] == "fail"
    assert d["caused_by"] is None
    assert d["remediation"][0] == {
        "step": "Install Node 22",
        "command": "nvm install 22",
        "safe_fix": True,
        "source": "manual",
        "files": [],
    }

def test_report_to_dict_nested_objects():
    rc = RootCause("node.sdk.version", "msg", ["a", "b"], "a → b")
    report = Report(
        repo_path="/repo", os="windows", mode="dep",
        summary={"total": 1, "pass": 0, "fail": 1, "skip": 0, "warnings": 0},
        checks=[CheckResult("a", "A", "node", status=CheckStatus.FAIL)],
        diagnosis=Diagnosis(root_causes=[rc]),
        exit_code=1,
    )
    d = report.to_dict()
    assert d["schema_version"] == "1.0"
    assert d["diagnosis"]["root_causes"][0]["cause_check_id"] == "node.sdk.version"
    assert d["exit_code"] == 1
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/unit/test_models.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'setup_doctor'`

- [ ] **Step 3: Create package scaffolding**

`pyproject.toml`:

```toml
[build-system]
requires = ["setuptools>=68"]
build-backend = "setuptools.build_meta"

[project]
name = "setup-doctor"
version = "0.1.0"
description = "Developer Setup Doctor: diagnose repo SDK/deps/service prerequisites with exact remediation steps"
requires-python = ">=3.11"
dependencies = []

[project.optional-dependencies]
ai = ["openai>=1.0", "anthropic>=0.25"]
dev = ["pytest>=8.0"]

[project.scripts]
setup-doctor = "setup_doctor.cli:main"

[tool.setuptools.packages.find]
where = ["src"]

[tool.pytest.ini_options]
testpaths = ["tests"]
```

`src/setup_doctor/__init__.py`:

```python
__version__ = "0.1.0"
```

- [ ] **Step 4: Write the models**

```python
# src/setup_doctor/models.py
from __future__ import annotations
from dataclasses import dataclass, field
from enum import Enum


class CheckStatus(str, Enum):
    PASS = "pass"
    FAIL = "fail"
    SKIP = "skip"


class Severity(str, Enum):
    ERROR = "error"
    WARNING = "warning"
    INFO = "info"


@dataclass
class RemediationStep:
    step: str
    command: str
    safe_fix: bool = False
    source: str = "manual"
    files: list[str] = field(default_factory=list)  # repo-relative files to back up before running

    def to_dict(self) -> dict:
        return {
            "step": self.step,
            "command": self.command,
            "safe_fix": self.safe_fix,
            "source": self.source,
            "files": list(self.files),
        }


@dataclass
class CheckResult:
    check_id: str
    name: str
    ecosystem: str
    severity: Severity = Severity.ERROR
    status: CheckStatus = CheckStatus.PASS
    evidence: str = ""
    remediation: list[RemediationStep] = field(default_factory=list)
    depends_on: list[str] = field(default_factory=list)
    caused_by: str | None = None

    def to_dict(self) -> dict:
        return {
            "check_id": self.check_id,
            "name": self.name,
            "ecosystem": self.ecosystem,
            "severity": self.severity.value,
            "status": self.status.value,
            "evidence": self.evidence,
            "remediation": [r.to_dict() for r in self.remediation],
            "depends_on": list(self.depends_on),
            "caused_by": self.caused_by,
        }


@dataclass
class RootCause:
    cause_check_id: str
    message: str
    affected_checks: list[str]
    chain: str

    def to_dict(self) -> dict:
        return {
            "cause_check_id": self.cause_check_id,
            "message": self.message,
            "affected_checks": list(self.affected_checks),
            "chain": self.chain,
        }


@dataclass
class Diagnosis:
    root_causes: list[RootCause] = field(default_factory=list)
    ai_explanation: str | None = None

    def to_dict(self) -> dict:
        return {
            "root_causes": [rc.to_dict() for rc in self.root_causes],
            "ai_explanation": self.ai_explanation,
        }


@dataclass
class Report:
    schema_version: str = "1.0"
    repo_path: str = ""
    os: str = ""
    mode: str = "dep"
    generated_at: str = ""
    summary: dict = field(default_factory=dict)
    checks: list[CheckResult] = field(default_factory=list)
    diagnosis: Diagnosis | None = None
    exit_code: int = 0

    def to_dict(self) -> dict:
        d = {
            "schema_version": self.schema_version,
            "repo_path": self.repo_path,
            "os": self.os,
            "mode": self.mode,
            "generated_at": self.generated_at,
            "summary": dict(self.summary),
            "checks": [c.to_dict() for c in self.checks],
        }
        if self.diagnosis is not None:
            d["diagnosis"] = self.diagnosis.to_dict()
        d["exit_code"] = self.exit_code
        return d
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `python -m pytest tests/unit/test_models.py -v`
Expected: 2 PASSED

- [ ] **Step 6: Commit**

```bash
git add pyproject.toml src/setup_doctor/__init__.py src/setup_doctor/models.py tests/unit/test_models.py
git commit -m "feat: project skeleton with normalized data models (CheckResult/Report/Diagnosis)"
```

---

## Task 2: Utils (commands, versions, osdetect)

**Files:**
- Create: `src/setup_doctor/utils/__init__.py`
- Create: `src/setup_doctor/utils/commands.py`
- Create: `src/setup_doctor/utils/versions.py`
- Create: `src/setup_doctor/utils/osdetect.py`
- Create: `tests/unit/test_utils.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/unit/test_utils.py
from setup_doctor.utils.commands import run_command, CommandResult
from setup_doctor.utils.versions import satisfies, parse_version

def test_run_command_captures_output():
    res = run_command(["python", "--version"], timeout=10)
    assert res.ok is True
    assert "Python" in res.stdout

def test_run_command_missing_binary():
    res = run_command(["definitely-not-a-command-xyz"], timeout=10)
    assert res.returncode == -1
    assert "not found" in res.stderr

def test_run_command_timeout():
    res = run_command(["python", "-c", "import time; time.sleep(5)"], timeout=1)
    assert res.returncode == -1
    assert "timed out" in res.stderr

def test_satisfies_semver():
    assert satisfies("v22.3.0", ">=20.0.0")
    assert not satisfies("18.16.0", ">=20.0.0")
    assert satisfies("21.0.2", "21")

def test_parse_version_extracts_numbers():
    assert parse_version("Node.js v20.11.1") == (20, 11, 1)
    assert parse_version("") == ()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/unit/test_utils.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'setup_doctor.utils'`

- [ ] **Step 3: Write the utils**

```python
# src/setup_doctor/utils/__init__.py
"""Shared helpers for command execution, version logic, and OS detection."""
```

```python
# src/setup_doctor/utils/commands.py
from __future__ import annotations
import shutil
import subprocess
import sys
from dataclasses import dataclass


@dataclass
class CommandResult:
    returncode: int
    stdout: str
    stderr: str

    @property
    def ok(self) -> bool:
        return self.returncode == 0


def which(name: str) -> str | None:
    return shutil.which(name)


def _run(cmd: list[str], cwd: str | None, timeout: int, env: dict | None) -> CommandResult:
    creationflags = subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0
    proc = subprocess.run(
        cmd, cwd=cwd, capture_output=True, text=True,
        timeout=timeout, env=env, creationflags=creationflags,
    )
    return CommandResult(proc.returncode, proc.stdout.strip(), proc.stderr.strip())


def run_command(cmd: list[str], cwd: str | None = None, timeout: int = 30, env: dict | None = None) -> CommandResult:
    try:
        return _run(cmd, cwd=cwd, timeout=timeout, env=env)
    except subprocess.TimeoutExpired:
        return CommandResult(-1, "", f"Command timed out after {timeout}s: {' '.join(cmd)}")
    except FileNotFoundError:
        return CommandResult(-1, "", f"Command not found: {cmd[0]}")
    except OSError as exc:
        return CommandResult(-1, "", f"OS error running {cmd[0]}: {exc}")
```

```python
# src/setup_doctor/utils/versions.py
from __future__ import annotations
import re

_VERSION_RE = re.compile(r"(\d+(?:\.\d+){0,3})")


def parse_version(s: str) -> tuple[int, ...]:
    """Extract the first dotted-numeric version from a string."""
    match = _VERSION_RE.search(s or "")
    if not match:
        return ()
    return tuple(int(p) for p in match.group(1).split("."))


def satisfies(installed: str, constraint: str) -> bool:
    """Check an installed version string against a constraint.

    Supports: ``>=X.Y.Z``, ``^X.Y.Z`` (major-pinned), and plain ``X`` (minimum major).
    """
    iv = parse_version(installed)
    c = constraint.strip()
    if not iv:
        return False
    if c.startswith(">="):
        return iv >= parse_version(c)
    if c.startswith("^"):
        cv = parse_version(c)
        return bool(cv) and iv[0] == cv[0] and iv >= cv
    cv = parse_version(c)
    return bool(cv) and iv >= cv
```

```python
# src/setup_doctor/utils/osdetect.py
from __future__ import annotations
import platform
import sys


def detect_os() -> str:
    system = platform.system().lower()
    if system == "windows":
        return "windows"
    if system == "darwin":
        return "macos"
    if system == "linux":
        return "linux"
    return sys.platform
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/unit/test_utils.py -v`
Expected: 5 PASSED

- [ ] **Step 5: Commit**

```bash
git add src/setup_doctor/utils tests/unit/test_utils.py
git commit -m "feat: utils for command running (timeout), semver comparison, OS detection"
```

---

## Task 3: Config (file > env > CLI)

**Files:**
- Create: `src/setup_doctor/config.py`
- Create: `tests/unit/test_config.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/unit/test_config.py
import os
import textwrap
import pytest
from setup_doctor.config import load_config


def test_defaults(tmp_path):
    cfg = load_config()
    assert cfg.default_mode == "dep"
    assert cfg.output_format == "text"
    assert cfg.ai.enabled is False
    assert cfg.ai.provider == "openai"
    assert cfg.ai.max_requests == 10


def test_config_file(tmp_path):
    cfg_file = tmp_path / "setup-doctor.toml"
    cfg_file.write_text(textwrap.dedent("""
        [mode]
        default = "flat"
        [ai]
        enabled = true
        provider = "anthropic"
        max_requests = 3
        [output]
        format = "json"
    """), encoding="utf-8")
    cfg = load_config(str(cfg_file))
    assert cfg.default_mode == "flat"
    assert cfg.ai.enabled is True
    assert cfg.ai.provider == "anthropic"
    assert cfg.ai.max_requests == 3
    assert cfg.output_format == "json"


def test_cli_overrides_file_and_env(tmp_path, monkeypatch):
    cfg_file = tmp_path / "setup-doctor.toml"
    cfg_file.write_text('[mode]\ndefault = "flat"\n', encoding="utf-8")
    monkeypatch.setenv("SETUP_DOCTOR_MODE", "flat")  # env same as file here
    cfg = load_config(str(cfg_file), overrides={"mode": "dep"})
    assert cfg.default_mode == "dep"  # CLI wins
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/unit/test_config.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'setup_doctor.config'`

- [ ] **Step 3: Write the config loader**

```python
# src/setup_doctor/config.py
from __future__ import annotations
import os
import tomllib
from dataclasses import dataclass, field


@dataclass
class AIConfig:
    enabled: bool = False
    provider: str = "openai"       # openai | anthropic
    model: str = "gpt-4o-mini"
    max_requests: int = 10
    timeout_sec: int = 20


@dataclass
class ToolConfig:
    default_mode: str = "dep"      # flat | dep
    output_format: str = "text"    # text | json
    ai: AIConfig = field(default_factory=AIConfig)


def load_config(path: str | None = None, overrides: dict | None = None) -> ToolConfig:
    cfg = ToolConfig()
    if path and os.path.isfile(path):
        with open(path, "rb") as f:
            data = tomllib.load(f)
        mode = data.get("mode", {})
        cfg.default_mode = mode.get("default", cfg.default_mode)
        out = data.get("output", {})
        cfg.output_format = out.get("format", cfg.output_format)
        ai = data.get("ai", {})
        cfg.ai.enabled = ai.get("enabled", cfg.ai.enabled)
        cfg.ai.provider = ai.get("provider", cfg.ai.provider)
        cfg.ai.model = ai.get("model", cfg.ai.model)
        cfg.ai.max_requests = ai.get("max_requests", cfg.ai.max_requests)
        cfg.ai.timeout_sec = ai.get("timeout_sec", cfg.ai.timeout_sec)
    # env: SETUP_DOCTOR_*
    cfg.default_mode = os.environ.get("SETUP_DOCTOR_MODE", cfg.default_mode)
    cfg.output_format = os.environ.get("SETUP_DOCTOR_FORMAT", cfg.output_format)
    cfg.ai.enabled = os.environ.get("SETUP_DOCTOR_AI", str(cfg.ai.enabled)).lower() in ("1", "true", "yes")
    ai_model = os.environ.get("SETUP_DOCTOR_AI_MODEL")
    if ai_model:
        cfg.ai.model = ai_model
    # CLI overrides win
    if overrides:
        if overrides.get("mode"):
            cfg.default_mode = overrides["mode"]
        if overrides.get("format"):
            cfg.output_format = overrides["format"]
        if overrides.get("ai") is not None:
            cfg.ai.enabled = overrides["ai"]
    return cfg
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/unit/test_config.py -v`
Expected: 3 PASSED

- [ ] **Step 5: Commit**

```bash
git add src/setup_doctor/config.py tests/unit/test_config.py
git commit -m "feat: config loader with precedence CLI > env > file > defaults"
```

---

## Task 4: Checker framework + registry + ecosystem detection

**Files:**
- Create: `src/setup_doctor/context.py`
- Create: `src/setup_doctor/checkers/__init__.py`
- Create: `src/setup_doctor/checkers/base.py`
- Create: `src/setup_doctor/registry.py`
- Create: `tests/unit/test_registry.py`

Note: `registry.py` imports the 6 checkers; create minimal stub checker modules now so imports resolve, then fill them in Tasks 5-10.

- [ ] **Step 1: Write the failing test**

```python
# tests/unit/test_registry.py
import os
import pytest
from setup_doctor.registry import detect_ecosystems, get_checkers


def make_repo(tmp_path, files):
    for rel in files:
        p = tmp_path / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text("{}", encoding="utf-8")
    return tmp_path


def test_detect_node_and_services(tmp_path):
    repo = make_repo(tmp_path, ["package.json", "docker-compose.yml", "src/main.ts"])
    assert detect_ecosystems(str(repo)) == {"node", "services"}


def test_detect_python(tmp_path):
    repo = make_repo(tmp_path, ["pyproject.toml", "src/app.py"])
    assert detect_ecosystems(str(repo)) == {"python"}


def test_detect_java_and_dotnet(tmp_path):
    repo = make_repo(tmp_path, ["pom.xml", "App.sln"])
    assert detect_ecosystems(str(repo)) == {"java", "dotnet"}


def test_detect_skips_vendor_dirs(tmp_path):
    repo = make_repo(tmp_path, ["package.json", "node_modules/pkg/index.js"])
    assert detect_ecosystems(str(repo)) == {"node"}


def test_get_checkers_returns_only_matching_ecosystems():
    checkers = get_checkers({"node", "registry"})
    eco = {c.ecosystem for c in checkers}
    assert eco == {"node", "registry"}
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/unit/test_registry.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'setup_doctor.registry'`

- [ ] **Step 3: Write framework + registry + checker stubs**

```python
# src/setup_doctor/context.py
from __future__ import annotations
from dataclasses import dataclass, field


@dataclass
class CheckContext:
    repo_path: str
    os: str
    config: object = None
    results: dict[str, object] = field(default_factory=dict)
```

```python
# src/setup_doctor/checkers/__init__.py
"""Checker plugins. Each module defines one Checker subclass per ecosystem."""
```

```python
# src/setup_doctor/checkers/base.py
from __future__ import annotations
from abc import ABC, abstractmethod
from ..models import CheckResult


class Checker(ABC):
    id: str = ""
    label: str = ""
    ecosystem: str = ""

    @property
    def depends_on(self) -> list[str]:
        return []

    @abstractmethod
    def run(self, ctx) -> list[CheckResult]:
        """Return all CheckResult objects for this ecosystem. MUST be read-only."""
```

```python
# src/setup_doctor/registry.py
from __future__ import annotations
import os

_CHECK_MARKERS = {
    "node": ("package.json",),
    "python": ("pyproject.toml", "requirements.txt", "setup.py", "setup.cfg", "Pipfile"),
    "java": ("pom.xml", "build.gradle", "build.gradle.kts", "settings.gradle"),
    "dotnet": ("*.sln", "*.csproj", "global.json"),
    "services": ("docker-compose.yml", "docker-compose.yaml", "compose.yml", "compose.yaml", ".env.example"),
}

_SKIP_DIRS = {"node_modules", "venv", ".venv", "__pycache__", ".git", ".idea", ".vscode"}


def _matches(name: str, pattern: str) -> bool:
    if "*" in pattern:
        return name.endswith(pattern.lstrip("*"))
    return name == pattern


def detect_ecosystems(repo_path: str) -> set[str]:
    """Scan the repo (pruning vendor dirs) and return detected ecosystems."""
    found: set[str] = set()
    for root, dirs, files in os.walk(repo_path):
        dirs[:] = sorted(d for d in dirs if d not in _SKIP_DIRS)
        for fname in files:
            for eco, patterns in _CHECK_MARKERS.items():
                if eco in found:
                    continue
                if any(_matches(fname, p) for p in patterns):
                    found.add(eco)
    # registry is always relevant for git repos; caller decides via get_checkers
    return found


def get_checkers(ecosystems: set[str]) -> list:
    from .checkers.node import NodeChecker
    from .checkers.python_ck import PythonChecker
    from .checkers.java import JavaChecker
    from .checkers.dotnet_ck import DotnetChecker
    from .checkers.services import ServicesChecker
    from .checkers.registry import RegistryChecker

    all_checkers = [
        NodeChecker(), PythonChecker(), JavaChecker(),
        DotnetChecker(), ServicesChecker(), RegistryChecker(),
    ]
    return [c for c in all_checkers if c.ecosystem in ecosystems]
```

Create minimal stub checkers so imports resolve (each will be replaced in Tasks 5-10):

```python
# src/setup_doctor/checkers/node.py   (stub, replaced in Task 5)
from .base import Checker

class NodeChecker(Checker):
    id, label, ecosystem = "node", "Node.js", "node"
    def run(self, ctx):
        return []
```

Repeat the stub pattern for `python_ck.py` (`PythonChecker`, ecosystem `"python"`), `java.py` (`JavaChecker`), `dotnet_ck.py` (`DotnetChecker`), `services.py` (`ServicesChecker`), `registry.py` (`RegistryChecker`, ecosystem `"registry"`).

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/unit/test_registry.py -v`
Expected: 5 PASSED

- [ ] **Step 5: Commit**

```bash
git add src/setup_doctor/context.py src/setup_doctor/registry.py src/setup_doctor/checkers tests/unit/test_registry.py
git commit -m "feat: checker framework + ecosystem detection + registry"
```

---

## Task 5: Node.js checker

**Files:**
- Modify: `src/setup_doctor/checkers/node.py` (replace stub)
- Create: `tests/unit/test_checkers.py`
- Create: `tests/conftest.py`

- [ ] **Step 1: Write the failing test + conftest helper**

```python
# tests/conftest.py
import json
import pytest
from setup_doctor.utils.commands import CommandResult


class FakeRunner:
    """Deterministic stand-in for run_command; keyed by command tuple."""
    def __init__(self):
        self.scripts: dict[tuple, CommandResult] = {}
        self.calls: list[list[str]] = []

    def set(self, cmd: list[str], result: CommandResult) -> None:
        self.scripts[tuple(cmd)] = result

    def __call__(self, cmd, cwd=None, timeout=30, env=None):
        self.calls.append(list(cmd))
        return self.scripts.get(tuple(cmd), CommandResult(0, "", ""))


@pytest.fixture
def fake_runner():
    return FakeRunner()


def write_json(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data), encoding="utf-8")
```

```python
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
    monkeypatch.setattr("setup_doctor.checkers.node.which",
                        lambda name: node_exe if name == "node" else ("C:\\node\\npm.cmd" if name == "npm" else None))
    monkeypatch.setattr("setup_doctor.checkers.node.run_command", fake_runner)


def test_node_pass(fake_runner, monkeypatch, tmp_path):
    repo = _node_context(tmp_path, {
        "package.json": '{"engines": {"node": ">=18.0.0"}, "scripts": {"build": "tsc"}}',
        "package-lock.json": "{}",
    })
    (repo / "node_modules").mkdir()
    fake_runner.set(["node", "--version"], CommandResult(0, "v22.3.0", ""))
    _patch(fake_runner, monkeypatch)
    results = NodeChecker().run(CheckContext(repo_path=str(repo), os="windows"))
    by_id = {r.check_id: r for r in results}
    assert by_id["node.runtime.present"].status == CheckStatus.PASS
    assert by_id["node.sdk.version"].status == CheckStatus.PASS
    assert by_id["node.lockfile.exists"].status == CheckStatus.PASS
    assert by_id["node.deps.installed"].status == CheckStatus.PASS
    assert by_id["node.build.run"].status == CheckStatus.PASS


def test_node_fail_sdk_and_deps(fake_runner, monkeypatch, tmp_path):
    repo = _node_context(tmp_path, {
        "package.json": '{"engines": {"node": ">=20.0.0"}, "scripts": {"build": "tsc"}}',
        "package-lock.json": "{}",
    })
    fake_runner.set(["node", "--version"], CommandResult(0, "v18.16.0", ""))
    _patch(fake_runner, monkeypatch)
    results = NodeChecker().run(CheckContext(repo_path=str(repo), os="windows"))
    by_id = {r.check_id: r for r in results}
    assert by_id["node.sdk.version"].status == CheckStatus.FAIL
    assert by_id["node.deps.installed"].status == CheckStatus.FAIL
    assert by_id["node.deps.installed"].remediation[0].command == "npm ci"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/unit/test_checkers.py -v`
Expected: FAIL (`NodeChecker.run` returns `[]`)

- [ ] **Step 3: Implement the Node checker**

```python
# src/setup_doctor/checkers/node.py
from __future__ import annotations
import json
import os
from .base import Checker
from ..models import CheckResult, RemediationStep, CheckStatus, Severity
from ..utils.commands import run_command, which
from ..utils.versions import satisfies


class NodeChecker(Checker):
    id, label, ecosystem = "node", "Node.js", "node"

    def _read_json(self, repo, name):
        path = os.path.join(repo, name)
        if not os.path.isfile(path):
            return None
        try:
            with open(path, encoding="utf-8") as f:
                return json.load(f)
        except (json.JSONDecodeError, OSError):
            return None

    def _required_version(self, repo):
        nvmrc = os.path.join(repo, ".nvmrc")
        if os.path.isfile(nvmrc):
            with open(nvmrc, encoding="utf-8") as f:
                return f.read().strip()
        pkg = self._read_json(repo, "package.json") or {}
        engines = pkg.get("engines") or {}
        return engines.get("node")

    def run(self, ctx):
        results = []
        node_exe = which("node")
        present = node_exe is not None
        results.append(CheckResult(
            check_id="node.runtime.present",
            name="Node.js runtime present",
            ecosystem=self.ecosystem,
            status=CheckStatus.PASS if present else CheckStatus.FAIL,
            evidence=f"node found at {node_exe}" if present else "node not found in PATH",
            remediation=[] if present else [
                RemediationStep("Install Node.js LTS",
                                "winget install OpenJS.NodeJS.LTS", safe_fix=False),
            ],
        ))

        version = ""
        if present:
            res = run_command([node_exe, "--version"], timeout=10)
            version = res.stdout

        required = self._required_version(ctx.repo_path)
        if not present:
            results.append(CheckResult(
                check_id="node.sdk.version", name="Node.js SDK version",
                ecosystem=self.ecosystem, status=CheckStatus.SKIP,
                evidence="skipped: runtime not present",
                depends_on=["node.runtime.present"],
            ))
        elif required is None:
            results.append(CheckResult(
                check_id="node.sdk.version", name="Node.js SDK version",
                ecosystem=self.ecosystem, status=CheckStatus.PASS,
                evidence=f"no version constraint found; node {version}",
                depends_on=["node.runtime.present"],
            ))
        else:
            ok = satisfies(version, required)
            results.append(CheckResult(
                check_id="node.sdk.version", name="Node.js SDK version",
                ecosystem=self.ecosystem,
                status=CheckStatus.PASS if ok else CheckStatus.FAIL,
                evidence=f"node {version} expected {required}",
                remediation=[] if ok else [
                    RemediationStep("Install the required Node version", "nvm install 22", safe_fix=False),
                    RemediationStep("Switch to it", "nvm use 22", safe_fix=False),
                ],
                depends_on=["node.runtime.present"],
            ))

        npm_exe = which("npm")
        results.append(CheckResult(
            check_id="node.pkgmgr.present", name="npm present",
            ecosystem=self.ecosystem,
            status=CheckStatus.PASS if npm_exe else CheckStatus.SKIP,
            evidence=f"npm at {npm_exe}" if npm_exe else "npm not found",
            remediation=[] if npm_exe else [
                RemediationStep("Enable corepack/npm", "corepack enable", safe_fix=False),
            ],
            depends_on=["node.runtime.present"],
        ))

        lockfile = next((n for n in ("package-lock.json", "yarn.lock", "pnpm-lock.yaml")
                         if os.path.isfile(os.path.join(ctx.repo_path, n))), None)
        results.append(CheckResult(
            check_id="node.lockfile.exists", name="Lockfile exists",
            ecosystem=self.ecosystem,
            status=CheckStatus.PASS if lockfile else CheckStatus.FAIL,
            evidence=f"found {lockfile}" if lockfile else "no lockfile found",
            remediation=[] if lockfile else [
                RemediationStep("Generate lockfile", "npm install --package-lock-only", safe_fix=False),
            ],
            depends_on=["node.pkgmgr.present"],
        ))

        node_modules_ok = os.path.isdir(os.path.join(ctx.repo_path, "node_modules"))
        results.append(CheckResult(
            check_id="node.deps.installed", name="Dependencies installed",
            ecosystem=self.ecosystem,
            status=CheckStatus.PASS if node_modules_ok else CheckStatus.FAIL,
            evidence="node_modules present" if node_modules_ok else "node_modules missing",
            remediation=[] if node_modules_ok else [
                RemediationStep("Install dependencies from lockfile", "npm ci", safe_fix=True),
            ],
            depends_on=["node.lockfile.exists", "node.sdk.version"],
        ))

        pkg = self._read_json(ctx.repo_path, "package.json") or {}
        scripts = pkg.get("scripts") or {}
        build_script = scripts.get("build")
        if not build_script:
            results.append(CheckResult(
                check_id="node.build.run", name="Build script runnable",
                ecosystem=self.ecosystem, status=CheckStatus.SKIP,
                evidence="no build script declared",
                depends_on=["node.deps.installed"],
            ))
        else:
            tool = build_script.split()[0]
            bin_path = os.path.join(ctx.repo_path, "node_modules", ".bin", tool)
            tool_ok = os.path.isfile(bin_path) or os.path.isfile(bin_path + ".cmd") or which(tool)
            results.append(CheckResult(
                check_id="node.build.run", name="Build script runnable",
                ecosystem=self.ecosystem,
                status=CheckStatus.PASS if tool_ok else CheckStatus.FAIL,
                evidence=f"build tool '{tool}' resolvable" if tool_ok else f"build tool '{tool}' not resolvable",
                remediation=[] if tool_ok else [
                    RemediationStep("Reinstall dependencies", "npm ci", safe_fix=True),
                ],
                depends_on=["node.deps.installed"],
            ))
        return results
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/unit/test_checkers.py -v`
Expected: 2 PASSED

- [ ] **Step 5: Commit**

```bash
git add src/setup_doctor/checkers/node.py tests/conftest.py tests/unit/test_checkers.py
git commit -m "feat: node checker (runtime, sdk version, lockfile, deps, build tool)"
```

---

## Task 6: Python checker

**Files:**
- Modify: `src/setup_doctor/checkers/python_ck.py` (replace stub)
- Modify: `tests/unit/test_checkers.py` (add python section)

- [ ] **Step 1: Write the failing test**

```python
# append to tests/unit/test_checkers.py
from setup_doctor.checkers.python_ck import PythonChecker


def test_python_pass(fake_runner, monkeypatch, tmp_path):
    repo = _node_context(tmp_path, {"pyproject.toml": '[project]\nrequires-python = ">=3.11"\n'})
    (repo / ".venv").mkdir()
    fake_runner.set(["py", "--version"], CommandResult(0, "Python 3.12.1", ""))
    monkeypatch.setattr("setup_doctor.checkers.python_ck.which",
                        lambda name: "C:\\Python\\py.exe" if name == "py" else None)
    monkeypatch.setattr("setup_doctor.checkers.python_ck.run_command", fake_runner)
    results = PythonChecker().run(CheckContext(repo_path=str(repo), os="windows"))
    by_id = {r.check_id: r for r in results}
    assert by_id["python.runtime.present"].status == CheckStatus.PASS
    assert by_id["python.version"].status == CheckStatus.PASS
    assert by_id["python.env.present"].status == CheckStatus.PASS


def test_python_fail_version(fake_runner, monkeypatch, tmp_path):
    repo = _node_context(tmp_path, {"pyproject.toml": '[project]\nrequires-python = ">=3.11"\n'})
    fake_runner.set(["py", "--version"], CommandResult(0, "Python 3.9.5", ""))
    monkeypatch.setattr("setup_doctor.checkers.python_ck.which",
                        lambda name: "C:\\Python\\py.exe" if name == "py" else None)
    monkeypatch.setattr("setup_doctor.checkers.python_ck.run_command", fake_runner)
    results = PythonChecker().run(CheckContext(repo_path=str(repo), os="windows"))
    assert {r.check_id for r in results if r.status == CheckStatus.FAIL} == {"python.version"}
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/unit/test_checkers.py -k python -v`
Expected: FAIL (`PythonChecker.run` returns `[]`)

- [ ] **Step 3: Implement the Python checker**

```python
# src/setup_doctor/checkers/python_ck.py
from __future__ import annotations
import os
import re
from .base import Checker
from ..models import CheckResult, RemediationStep, CheckStatus
from ..utils.commands import run_command, which
from ..utils.versions import satisfies


class PythonChecker(Checker):
    id, label, ecosystem = "python", "Python", "python"

    def _required_version(self, repo):
        pyproject = os.path.join(repo, "pyproject.toml")
        if os.path.isfile(pyproject):
            text = open(pyproject, encoding="utf-8").read()
            m = re.search(r'requires-python\s*=\s*["\']([^"\']+)["\']', text)
            if m:
                return m.group(1)
        ver_file = os.path.join(repo, ".python-version")
        if os.path.isfile(ver_file):
            return open(ver_file, encoding="utf-8").read().strip()
        return None

    def run(self, ctx):
        results = []
        py_exe = which("py") or which("python")
        present = py_exe is not None
        results.append(CheckResult(
            check_id="python.runtime.present", name="Python runtime present",
            ecosystem=self.ecosystem,
            status=CheckStatus.PASS if present else CheckStatus.FAIL,
            evidence=f"python at {py_exe}" if present else "no python/py found in PATH",
            remediation=[] if present else [
                RemediationStep("Install Python", "winget install Python.Python.3.12", safe_fix=False),
            ],
        ))

        version = ""
        if present:
            res = run_command([py_exe, "--version"], timeout=10)
            version = res.stdout

        required = self._required_version(ctx.repo_path)
        if not present:
            results.append(CheckResult(
                check_id="python.version", name="Python version",
                ecosystem=self.ecosystem, status=CheckStatus.SKIP,
                evidence="skipped: runtime not present",
                depends_on=["python.runtime.present"],
            ))
        elif required is None:
            results.append(CheckResult(
                check_id="python.version", name="Python version",
                ecosystem=self.ecosystem, status=CheckStatus.PASS,
                evidence=f"no constraint; found {version}",
                depends_on=["python.runtime.present"],
            ))
        else:
            ok = satisfies(version, required)
            results.append(CheckResult(
                check_id="python.version", name="Python version",
                ecosystem=self.ecosystem,
                status=CheckStatus.PASS if ok else CheckStatus.FAIL,
                evidence=f"found {version} expected {required}",
                remediation=[] if ok else [
                    RemediationStep("Install the required Python version",
                                    "py -3.12", safe_fix=False),
                ],
                depends_on=["python.runtime.present"],
            ))

        venv_dir = os.path.join(ctx.repo_path, ".venv")
        venv_ok = os.path.isfile(os.path.join(venv_dir, "pyvenv.cfg"))
        results.append(CheckResult(
            check_id="python.env.present", name="Virtual env present",
            ecosystem=self.ecosystem,
            status=CheckStatus.PASS if venv_ok else CheckStatus.FAIL,
            evidence=".venv with pyvenv.cfg present" if venv_ok else ".venv missing",
            remediation=[] if venv_ok else [
                RemediationStep("Create a virtual environment", "py -m venv .venv",
                                safe_fix=True, files=[".venv"]),
            ],
            depends_on=["python.runtime.present"],
        ))

        req_path = os.path.join(ctx.repo_path, "requirements.txt")
        if not os.path.isfile(req_path):
            results.append(CheckResult(
                check_id="python.deps.installed", name="Dependencies installed",
                ecosystem=self.ecosystem, status=CheckStatus.SKIP,
                evidence="no requirements.txt; skipping",
                depends_on=["python.env.present"],
            ))
        else:
            reqs = [ln.strip() for ln in open(req_path, encoding="utf-8")
                    if ln.strip() and not ln.startswith("#")]
            pip = os.path.join(venv_dir, "Scripts", "pip.exe") if venv_ok else None
            missing: list[str] = []
            if pip:
                res = run_command([pip, "list"], timeout=30)
                installed = res.stdout.lower()
                for r in reqs:
                    pkg = re.split(r"[<>=!~\[;]", r)[0].strip()
                    if pkg and pkg.lower() not in installed:
                        missing.append(pkg)
            results.append(CheckResult(
                check_id="python.deps.installed", name="Dependencies installed",
                ecosystem=self.ecosystem,
                status=CheckStatus.PASS if not missing else CheckStatus.FAIL,
                evidence=f"missing: {', '.join(missing)}" if missing else "requirements satisfied",
                remediation=[] if not missing else [
                    RemediationStep("Install dependencies", "pip install -r requirements.txt",
                                    safe_fix=True),
                ],
                depends_on=["python.env.present"],
            ))
        return results
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/unit/test_checkers.py -k python -v`
Expected: 2 PASSED

- [ ] **Step 5: Commit**

```bash
git add src/setup_doctor/checkers/python_ck.py tests/unit/test_checkers.py
git commit -m "feat: python checker (runtime, version, venv, deps)"
```

---

## Task 7: Java checker

**Files:**
- Modify: `src/setup_doctor/checkers/java.py` (replace stub)
- Modify: `tests/unit/test_checkers.py` (add java section)

- [ ] **Step 1: Write the failing test**

```python
# append to tests/unit/test_checkers.py
from setup_doctor.checkers.java import JavaChecker


def test_java_pass(fake_runner, monkeypatch, tmp_path):
    repo = _node_context(tmp_path, {"pom.xml": "<project><properties><maven.compiler.release>17</maven.compiler.release></properties></project>"})
    fake_runner.set(["java", "-version"], CommandResult(0, "openjdk version \"17.0.9\" 2023-10-17", ""))
    fake_runner.set(["mvn", "-q", "dependency:resolve"], CommandResult(0, "", ""))
    monkeypatch.setattr("setup_doctor.checkers.java.which", lambda name: "C:\\java\\java.exe" if name == "java" else ("C:\\maven\\mvn.cmd" if name == "mvn" else None))
    monkeypatch.setattr("setup_doctor.checkers.java.run_command", fake_runner)
    results = JavaChecker().run(CheckContext(repo_path=str(repo), os="windows"))
    assert {r.check_id for r in results if r.status == CheckStatus.FAIL} == set()


def test_java_fail_version(fake_runner, monkeypatch, tmp_path):
    repo = _node_context(tmp_path, {"pom.xml": "<project><properties><maven.compiler.release>21</maven.compiler.release></properties></project>"})
    fake_runner.set(["java", "-version"], CommandResult(0, 'openjdk version "11.0.20" 2023-07-18', ""))
    fake_runner.set(["mvn", "-q", "dependency:resolve"], CommandResult(0, "", ""))
    monkeypatch.setattr("setup_doctor.checkers.java.which", lambda name: "C:\\java\\java.exe" if name == "java" else ("C:\\maven\\mvn.cmd" if name == "mvn" else None))
    monkeypatch.setattr("setup_doctor.checkers.java.run_command", fake_runner)
    results = JavaChecker().run(CheckContext(repo_path=str(repo), os="windows"))
    assert {r.check_id for r in results if r.status == CheckStatus.FAIL} == {"java.version"}
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/unit/test_checkers.py -k java -v`
Expected: FAIL

- [ ] **Step 3: Implement the Java checker**

```python
# src/setup_doctor/checkers/java.py
from __future__ import annotations
import os
import re
from .base import Checker
from ..models import CheckResult, RemediationStep, CheckStatus
from ..utils.commands import run_command, which


class JavaChecker(Checker):
    id, label, ecosystem = "java", "Java", "java"

    def _required_major(self, repo):
        pom = os.path.join(repo, "pom.xml")
        if os.path.isfile(pom):
            text = open(pom, encoding="utf-8").read()
            m = re.search(r"<maven\.compiler\.release>(\d+)</maven\.compiler\.release>", text)
            if m:
                return int(m.group(1))
            m = re.search(r"<java\.version>(\d+)</java\.version>", text)
            if m:
                return int(m.group(1))
        return None

    def run(self, ctx):
        results = []
        java_exe = which("java")
        present = java_exe is not None
        results.append(CheckResult(
            check_id="java.runtime.present", name="JDK present",
            ecosystem=self.ecosystem,
            status=CheckStatus.PASS if present else CheckStatus.FAIL,
            evidence=f"java at {java_exe}" if present else "java not found in PATH",
            remediation=[] if present else [
                RemediationStep("Install a JDK", "winget install EclipseAdoptium.Temurin.21.JDK", safe_fix=False),
            ],
        ))

        version = ""
        if present:
            res = run_command([java_exe, "-version"], timeout=10)
            version = res.stderr or res.stdout

        required = self._required_major(ctx.repo_path)
        if not present:
            results.append(CheckResult(
                check_id="java.version", name="JDK version",
                ecosystem=self.ecosystem, status=CheckStatus.SKIP,
                evidence="skipped: runtime not present",
                depends_on=["java.runtime.present"],
            ))
        elif required is None:
            results.append(CheckResult(
                check_id="java.version", name="JDK version",
                ecosystem=self.ecosystem, status=CheckStatus.PASS,
                evidence=f"no java version constraint; found {version}",
                depends_on=["java.runtime.present"],
            ))
        else:
            m = re.search(r'version "(\d+)', version)
            major = int(m.group(1)) if m else 0
            ok = major == required
            results.append(CheckResult(
                check_id="java.version", name="JDK version",
                ecosystem=self.ecosystem,
                status=CheckStatus.PASS if ok else CheckStatus.FAIL,
                evidence=f"found JDK {major} expected {required}",
                remediation=[] if ok else [
                    RemediationStep("Install JDK {required}", "winget install EclipseAdoptium.Temurin.{required}.JDK".format(required=required), safe_fix=False),
                ],
                depends_on=["java.runtime.present"],
            ))

        has_wrapper = os.path.isfile(os.path.join(ctx.repo_path, "mvnw")) or os.path.isfile(os.path.join(ctx.repo_path, "gradlew"))
        mvn = which("mvn")
        gradle = which("gradle")
        tool_ok = has_wrapper or mvn or gradle
        results.append(CheckResult(
            check_id="java.maven.gradle.present", name="Maven/Gradle present",
            ecosystem=self.ecosystem,
            status=CheckStatus.PASS if tool_ok else CheckStatus.FAIL,
            evidence="wrapper or mvn/gradle found" if tool_ok else "neither wrapper nor mvn/gradle found",
            remediation=[] if tool_ok else [
                RemediationStep("Install Maven", "winget install Apache.Maven", safe_fix=False),
            ],
            depends_on=["java.runtime.present"],
        ))

        if mvn:
            res = run_command(["mvn", "-q", "dependency:resolve"], cwd=ctx.repo_path, timeout=60)
            results.append(CheckResult(
                check_id="java.deps.resolved", name="Dependencies resolved",
                ecosystem=self.ecosystem,
                status=CheckStatus.PASS if res.ok else CheckStatus.FAIL,
                evidence=res.stderr[-200:] if not res.ok else "mvn dependency:resolve succeeded",
                remediation=[] if res.ok else [
                    RemediationStep("Resolve dependencies / check network", "mvn dependency:resolve", safe_fix=True),
                ],
                depends_on=["java.maven.gradle.present"],
            ))
        else:
            results.append(CheckResult(
                check_id="java.deps.resolved", name="Dependencies resolved",
                ecosystem=self.ecosystem, status=CheckStatus.SKIP,
                evidence="no maven; skipped",
                depends_on=["java.maven.gradle.present"],
            ))
        return results
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/unit/test_checkers.py -k java -v`
Expected: 2 PASSED

- [ ] **Step 5: Commit**

```bash
git add src/setup_doctor/checkers/java.py tests/unit/test_checkers.py
git commit -m "feat: java checker (JDK, version, maven/gradle, dependency resolution)"
```

---

## Task 8: .NET checker

**Files:**
- Modify: `src/setup_doctor/checkers/dotnet_ck.py` (replace stub)
- Modify: `tests/unit/test_checkers.py` (add dotnet section)

- [ ] **Step 1: Write the failing test**

```python
# append to tests/unit/test_checkers.py
from setup_doctor.checkers.dotnet_ck import DotnetChecker


def test_dotnet_pass(fake_runner, monkeypatch, tmp_path):
    repo = _node_context(tmp_path, {"global.json": '{"sdk": {"version": "8.0.100"}}'})
    fake_runner.set(["dotnet", "--list-sdks"], CommandResult(0, "8.0.100 [C:\\dotnet\\sdk]", ""))
    fake_runner.set(["dotnet", "restore"], CommandResult(0, "", ""))
    monkeypatch.setattr("setup_doctor.checkers.dotnet_ck.which", lambda name: "C:\\dotnet\\dotnet.exe" if name == "dotnet" else None)
    monkeypatch.setattr("setup_doctor.checkers.dotnet_ck.run_command", fake_runner)
    results = DotnetChecker().run(CheckContext(repo_path=str(repo), os="windows"))
    assert {r.check_id for r in results if r.status == CheckStatus.FAIL} == set()


def test_dotnet_fail_missing_sdk(fake_runner, monkeypatch, tmp_path):
    repo = _node_context(tmp_path, {"global.json": '{"sdk": {"version": "9.0.100"}}'})
    fake_runner.set(["dotnet", "--list-sdks"], CommandResult(0, "8.0.100 [C:\\dotnet\\sdk]", ""))
    fake_runner.set(["dotnet", "restore"], CommandResult(0, "", ""))
    monkeypatch.setattr("setup_doctor.checkers.dotnet_ck.which", lambda name: "C:\\dotnet\\dotnet.exe" if name == "dotnet" else None)
    monkeypatch.setattr("setup_doctor.checkers.dotnet_ck.run_command", fake_runner)
    results = DotnetChecker().run(CheckContext(repo_path=str(repo), os="windows"))
    assert {r.check_id for r in results if r.status == CheckStatus.FAIL} == {"dotnet.sdk.version"}
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/unit/test_checkers.py -k dotnet -v`
Expected: FAIL

- [ ] **Step 3: Implement the .NET checker**

```python
# src/setup_doctor/checkers/dotnet_ck.py
from __future__ import annotations
import json
import os
import re
from .base import Checker
from ..models import CheckResult, RemediationStep, CheckStatus
from ..utils.commands import run_command, which


class DotnetChecker(Checker):
    id, label, ecosystem = "dotnet", ".NET", "dotnet"

    def _required_version(self, repo):
        gj = os.path.join(repo, "global.json")
        if os.path.isfile(gj):
            try:
                data = json.load(open(gj, encoding="utf-8"))
                return (data.get("sdk") or {}).get("version")
            except (json.JSONDecodeError, OSError):
                return None
        return None

    def run(self, ctx):
        results = []
        dt = which("dotnet")
        present = dt is not None
        results.append(CheckResult(
            check_id="dotnet.runtime.present", name="dotnet CLI present",
            ecosystem=self.ecosystem,
            status=CheckStatus.PASS if present else CheckStatus.FAIL,
            evidence=f"dotnet at {dt}" if present else "dotnet not found in PATH",
            remediation=[] if present else [
                RemediationStep("Install the .NET SDK", "winget install Microsoft.DotNet.SDK.8", safe_fix=False),
            ],
        ))

        installed = ""
        if present:
            res = run_command([dt, "--list-sdks"], timeout=10)
            installed = res.stdout

        required = self._required_version(ctx.repo_path)
        if not present:
            results.append(CheckResult(
                check_id="dotnet.sdk.version", name=".NET SDK version",
                ecosystem=self.ecosystem, status=CheckStatus.SKIP,
                evidence="skipped: cli not present",
                depends_on=["dotnet.runtime.present"],
            ))
        elif required is None:
            results.append(CheckResult(
                check_id="dotnet.sdk.version", name=".NET SDK version",
                ecosystem=self.ecosystem, status=CheckStatus.PASS,
                evidence="no global.json constraint",
                depends_on=["dotnet.runtime.present"],
            ))
        else:
            ok = any(line.strip().startswith(required) for line in installed.splitlines())
            results.append(CheckResult(
                check_id="dotnet.sdk.version", name=".NET SDK version",
                ecosystem=self.ecosystem,
                status=CheckStatus.PASS if ok else CheckStatus.FAIL,
                evidence=f"required {required}; installed: {installed or '(none)'}",
                remediation=[] if ok else [
                    RemediationStep("Install the pinned .NET SDK", "winget install Microsoft.DotNet.SDK.{required}".format(required=required.split(".")[0]), safe_fix=False),
                ],
                depends_on=["dotnet.runtime.present"],
            ))

        if present:
            res = run_command([dt, "restore"], cwd=ctx.repo_path, timeout=60)
            results.append(CheckResult(
                check_id="dotnet.restore", name="NuGet restore",
                ecosystem=self.ecosystem,
                status=CheckStatus.PASS if res.ok else CheckStatus.FAIL,
                evidence=res.stderr[-200:] if not res.ok else "dotnet restore succeeded",
                remediation=[] if res.ok else [
                    RemediationStep("Restore packages / check nuget.config", "dotnet restore", safe_fix=True),
                ],
                depends_on=["dotnet.sdk.version"],
            ))
        else:
            results.append(CheckResult(
                check_id="dotnet.restore", name="NuGet restore",
                ecosystem=self.ecosystem, status=CheckStatus.SKIP,
                evidence="skipped: cli not present",
                depends_on=["dotnet.sdk.version"],
            ))
        return results
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/unit/test_checkers.py -k dotnet -v`
Expected: 2 PASSED

- [ ] **Step 5: Commit**

```bash
git add src/setup_doctor/checkers/dotnet_ck.py tests/unit/test_checkers.py
git commit -m "feat: dotnet checker (cli, pinned sdk version, restore)"
```

---

## Task 9: Services checker

**Files:**
- Modify: `src/setup_doctor/checkers/services.py` (replace stub)
- Modify: `tests/unit/test_checkers.py` (add services section)

- [ ] **Step 1: Write the failing test**

```python
# append to tests/unit/test_checkers.py
from setup_doctor.checkers.services import ServicesChecker


def test_services_fail_no_env(fake_runner, monkeypatch, tmp_path):
    repo = _node_context(tmp_path, {
        "docker-compose.yml": "services:\n  db:\n    image: postgres:16\n  redis:\n    image: redis:7\n",
        ".env.example": "DATABASE_URL=postgres://localhost:5432/app",
    })
    fake_runner.set(["docker", "info"], CommandResult(0, "Server Version: 26.0.0", ""))
    fake_runner.set(["docker", "compose", "ps", "--format", "{{.Name}}"], CommandResult(0, "repo-db-1\nrepo-redis-1", ""))
    monkeypatch.setattr("setup_doctor.checkers.services.which", lambda name: "C:\\docker\\docker.exe" if name == "docker" else None)
    monkeypatch.setattr("setup_doctor.checkers.services.run_command", fake_runner)
    results = ServicesChecker().run(CheckContext(repo_path=str(repo), os="windows"))
    by_id = {r.check_id: r for r in results}
    assert by_id["services.envfile"].status == CheckStatus.FAIL  # .env missing
    assert by_id["services.compose.up"].status == CheckStatus.PASS


def test_services_db_port_closed(fake_runner, monkeypatch, tmp_path):
    repo = _node_context(tmp_path, {"docker-compose.yml": "services:\n  db:\n    image: postgres:16\n"})
    fake_runner.set(["docker", "info"], CommandResult(0, "Server Version: 26.0.0", ""))
    fake_runner.set(["docker", "compose", "ps", "--format", "{{.Name}}"], CommandResult(0, "repo-db-1", ""))
    monkeypatch.setattr("setup_doctor.checkers.services.which", lambda name: "C:\\docker\\docker.exe" if name == "docker" else None)
    monkeypatch.setattr("setup_doctor.checkers.services.run_command", fake_runner)
    monkeypatch.setattr("setup_doctor.checkers.services._port_open", lambda host, port: False)
    results = ServicesChecker().run(CheckContext(repo_path=str(repo), os="windows"))
    assert results[2].check_id == "services.db.port"
    assert results[2].status == CheckStatus.FAIL
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/unit/test_checkers.py -k services -v`
Expected: FAIL

- [ ] **Step 3: Implement the Services checker**

```python
# src/setup_doctor/checkers/services.py
from __future__ import annotations
import os
import socket
import yaml  # PyYAML is a runtime dependency for this checker
from .base import Checker
from ..models import CheckResult, RemediationStep, CheckStatus
from ..utils.commands import run_command, which


def _port_open(host: str, port: int, timeout: float = 3.0) -> bool:
    try:
        with socket.create_connection((host, port), timeout=timeout):
            return True
    except OSError:
        return False


class ServicesChecker(Checker):
    id, label, ecosystem = "services", "Local services", "services"

    def _compose_services(self, repo):
        for name in ("docker-compose.yml", "docker-compose.yaml", "compose.yml", "compose.yaml"):
            path = os.path.join(repo, name)
            if os.path.isfile(path):
                try:
                    data = yaml.safe_load(open(path, encoding="utf-8"))
                    return (data.get("services") or {}).keys()
                except yaml.YAMLError:
                    return []
        return []

    def run(self, ctx):
        results = []
        has_compose = bool(self._compose_services(ctx.repo_path))
        docker = which("docker")
        docker_ok = docker is not None and run_command([docker, "info"], timeout=10).ok
        results.append(CheckResult(
            check_id="services.container.present", name="Docker daemon reachable",
            ecosystem=self.ecosystem,
            status=CheckStatus.PASS if docker_ok else CheckStatus.SKIP,
            evidence="docker daemon reachable" if docker_ok else "docker missing/unavailable",
            remediation=[] if docker_ok else [
                RemediationStep("Start Docker Desktop", "start \"\" \"C:\\Program Files\\Docker\\Docker\\Docker Desktop.exe\"", safe_fix=False),
            ],
        ))

        expected = set(self._compose_services(ctx.repo_path))
        if docker_ok and expected:
            res = run_command([docker, "compose", "ps", "--format", "{{.Name}}"], cwd=ctx.repo_path, timeout=30)
            running = set(res.stdout.splitlines())
            missing = expected - running if res.ok else expected
            results.append(CheckResult(
                check_id="services.compose.up", name="Compose services running",
                ecosystem=self.ecosystem,
                status=CheckStatus.PASS if not missing else CheckStatus.FAIL,
                evidence=f"not running: {', '.join(sorted(missing))}" if missing else "all compose services running",
                remediation=[] if not missing else [
                    RemediationStep("Start compose services", "docker compose up -d", safe_fix=True),
                ],
                depends_on=["services.container.present"],
            ))
        else:
            results.append(CheckResult(
                check_id="services.compose.up", name="Compose services running",
                ecosystem=self.ecosystem, status=CheckStatus.SKIP,
                evidence="no compose file / docker unavailable",
                depends_on=["services.container.present"],
            ))

        # DB/Redis port checks (read-only TCP probe)
        port_checks = [
            ("services.db.port", 5432, "PostgreSQL", "db"),
            ("services.redis", 6379, "Redis", "redis"),
        ]
        for check_id, port, label, key in port_checks:
            if key in expected:
                ok = _port_open("127.0.0.1", port)
                results.append(CheckResult(
                    check_id=check_id, name=f"{label} reachable",
                    ecosystem=self.ecosystem,
                    status=CheckStatus.PASS if ok else CheckStatus.FAIL,
                    evidence=f"port {port} {'open' if ok else 'closed'}",
                    remediation=[] if ok else [
                        RemediationStep(f"Start {label}", f"docker compose up -d {key}", safe_fix=True),
                    ],
                    depends_on=["services.compose.up"],
                ))
            else:
                results.append(CheckResult(
                    check_id=check_id, name=f"{label} reachable",
                    ecosystem=self.ecosystem, status=CheckStatus.SKIP,
                    evidence="service not declared in compose",
                    depends_on=["services.compose.up"],
                ))

        env_path = os.path.join(ctx.repo_path, ".env")
        env_example = os.path.join(ctx.repo_path, ".env.example")
        if os.path.isfile(env_path):
            results.append(CheckResult(
                check_id="services.envfile", name=".env file present",
                ecosystem=self.ecosystem, status=CheckStatus.PASS,
                evidence=".env exists",
            ))
        elif os.path.isfile(env_example):
            results.append(CheckResult(
                check_id="services.envfile", name=".env file present",
                ecosystem=self.ecosystem, status=CheckStatus.FAIL,
                evidence=".env missing but .env.example exists",
                remediation=[RemediationStep("Create .env from template", "copy .env.example .env",
                                             safe_fix=True, files=[".env"])],
            ))
        else:
            results.append(CheckResult(
                check_id="services.envfile", name=".env file present",
                ecosystem=self.ecosystem, status=CheckStatus.SKIP,
                evidence="no .env template present",
            ))
        return results
```

Note: this checker uses `yaml`; add `PyYAML` to `dependencies` in `pyproject.toml`:

```toml
dependencies = ["PyYAML>=6.0"]
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pip install -e ".[dev]"` then `python -m pytest tests/unit/test_checkers.py -k services -v`
Expected: 2 PASSED

- [ ] **Step 5: Commit**

```bash
git add pyproject.toml src/setup_doctor/checkers/services.py tests/unit/test_checkers.py
git commit -m "feat: services checker (docker, compose, db/redis port probes, .env)"
```

---

## Task 10: Registry/credentials checker

**Files:**
- Modify: `src/setup_doctor/checkers/registry.py` (replace stub)
- Modify: `tests/unit/test_checkers.py` (add registry section)

- [ ] **Step 1: Write the failing test**

```python
# append to tests/unit/test_checkers.py
from setup_doctor.checkers.registry import RegistryChecker


def test_registry_git_user_and_ssh(fake_runner, monkeypatch, tmp_path):
    repo = _node_context(tmp_path, {})
    fake_runner.set(["git", "config", "--get", "user.name"], CommandResult(0, "Alice", ""))
    fake_runner.set(["git", "config", "--get", "user.email"], CommandResult(0, "alice@example.com", ""))
    monkeypatch.setattr("setup_doctor.checkers.registry.which", lambda name: "C:\\git\\git.exe" if name == "git" else None)
    monkeypatch.setattr("setup_doctor.checkers.registry.run_command", fake_runner)
    monkeypatch.setattr("setup_doctor.checkers.registry._ssh_key_exists", lambda: True)
    results = RegistryChecker().run(CheckContext(repo_path=str(repo), os="windows", config=object()))
    by_id = {r.check_id: r for r in results}
    assert by_id["registry.git.user"].status == CheckStatus.PASS
    assert by_id["registry.git.ssh"].status == CheckStatus.PASS
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/unit/test_checkers.py -k registry -v`
Expected: FAIL

- [ ] **Step 3: Implement the Registry checker**

```python
# src/setup_doctor/checkers/registry.py
from __future__ import annotations
import os
from .base import Checker
from ..models import CheckResult, RemediationStep, CheckStatus
from ..utils.commands import run_command, which

_SSH_KEYS = ("id_ed25519", "id_rsa", "id_ecdsa")


def _ssh_key_exists() -> bool:
    home = os.path.expanduser("~")
    return any(os.path.isfile(os.path.join(home, ".ssh", k)) for k in _SSH_KEYS)


class RegistryChecker(Checker):
    id, label, ecosystem = "registry", "Registry/credentials", "registry"

    def run(self, ctx):
        results = []
        git = which("git")
        if git:
            name = run_command([git, "config", "--get", "user.name"], timeout=10)
            email = run_command([git, "config", "--get", "user.email"], timeout=10)
            ok = name.ok and email.ok
            results.append(CheckResult(
                check_id="registry.git.user", name="git user configured",
                ecosystem=self.ecosystem,
                status=CheckStatus.PASS if ok else CheckStatus.FAIL,
                evidence="user.name/email set" if ok else "git user.name/email not set",
                remediation=[] if ok else [
                    RemediationStep("Set git identity",
                                    'git config --global user.name "Your Name" && git config --global user.email "you@example.com"',
                                    safe_fix=False),
                ],
            ))
        else:
            results.append(CheckResult(
                check_id="registry.git.user", name="git user configured",
                ecosystem=self.ecosystem, status=CheckStatus.SKIP,
                evidence="git not found",
            ))

        ssh_ok = _ssh_key_exists()
        results.append(CheckResult(
            check_id="registry.git.ssh", name="SSH key present",
            ecosystem=self.ecosystem,
            status=CheckStatus.PASS if ssh_ok else CheckStatus.FAIL,
            evidence="ssh key found" if ssh_ok else "no ssh key in ~/.ssh",
            remediation=[] if ssh_ok else [
                RemediationStep("Generate an SSH key", "ssh-keygen -t ed25519 -C \"you@example.com\"", safe_fix=False),
            ],
        ))

        npmrc = os.path.join(ctx.repo_path, ".npmrc")
        if os.path.isfile(npmrc):
            npm = which("npm")
            expected = ""
            with open(npmrc, encoding="utf-8") as f:
                for line in f:
                    if line.startswith("registry="):
                        expected = line.split("=", 1)[1].strip()
            if npm and expected:
                res = run_command([npm, "config", "get", "registry"], timeout=10)
                ok = res.stdout.strip() == expected
                results.append(CheckResult(
                    check_id="registry.npm", name="npm registry configured",
                    ecosystem=self.ecosystem,
                    status=CheckStatus.PASS if ok else CheckStatus.FAIL,
                    evidence=f"expected {expected}; got {res.stdout.strip()}",
                    remediation=[] if ok else [
                        RemediationStep("Point npm to the required registry",
                                        f"npm config set registry {expected}", safe_fix=False),
                    ],
                ))
            else:
                results.append(CheckResult(
                    check_id="registry.npm", name="npm registry configured",
                    ecosystem=self.ecosystem, status=CheckStatus.SKIP,
                    evidence="npm not found or no registry line in .npmrc",
                ))
        else:
            results.append(CheckResult(
                check_id="registry.npm", name="npm registry configured",
                ecosystem=self.ecosystem, status=CheckStatus.SKIP,
                evidence="no .npmrc in repo",
            ))

        pypi = os.path.join(ctx.repo_path, "pip.conf")
        if os.path.isfile(pypi):
            py = which("py") or which("python")
            results.append(CheckResult(
                check_id="registry.pypi", name="pip index configured",
                ecosystem=self.ecosystem,
                status=CheckStatus.PASS if py else CheckStatus.SKIP,
                evidence="pip.conf exists" if py else "python not found",
                remediation=[RemediationStep("Point pip at the required index",
                                             "pip config set global.index-url <url>", safe_fix=False)],
            ))
        else:
            results.append(CheckResult(
                check_id="registry.pypi", name="pip index configured",
                ecosystem=self.ecosystem, status=CheckStatus.SKIP,
                evidence="no pip.conf in repo",
            ))
        return results
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/unit/test_checkers.py -k registry -v`
Expected: 1 PASSED

- [ ] **Step 5: Commit**

```bash
git add src/setup_doctor/checkers/registry.py tests/unit/test_checkers.py
git commit -m "feat: registry checker (git identity, ssh key, npm/pip registries)"
```

---

## Task 11: Diagnosis Engine — flat mode + summary + exit code

**Files:**
- Create: `src/setup_doctor/engine.py`
- Create: `tests/unit/test_engine.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/unit/test_engine.py
from setup_doctor.engine import diagnose
from setup_doctor.models import CheckResult, CheckStatus, Severity


def _checks():
    return [
        CheckResult("a", "A", "node", status=CheckStatus.PASS),
        CheckResult("b", "B", "node", status=CheckStatus.FAIL, severity=Severity.ERROR),
        CheckResult("c", "C", "node", status=CheckStatus.SKIP),
    ]


def test_flat_report_has_no_diagnosis():
    report = diagnose(_checks(), "flat", "/repo", "windows")
    assert report.mode == "flat"
    assert report.diagnosis is None
    assert report.summary["total"] == 3
    assert report.summary["pass"] == 1
    assert report.summary["fail"] == 1
    assert report.summary["skip"] == 1


def test_exit_code_1_when_error_fail():
    report = diagnose(_checks(), "flat", "/repo", "windows")
    assert report.exit_code == 1


def test_exit_code_0_when_all_pass():
    checks = [CheckResult("a", "A", "node", status=CheckStatus.PASS)]
    report = diagnose(checks, "flat", "/repo", "windows")
    assert report.exit_code == 0


def test_warning_fail_does_not_set_exit_1():
    checks = [CheckResult("w", "W", "node", status=CheckStatus.FAIL, severity=Severity.WARNING)]
    report = diagnose(checks, "flat", "/repo", "windows")
    assert report.exit_code == 0
    assert report.summary["warnings"] == 1
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/unit/test_engine.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'setup_doctor.engine'`

- [ ] **Step 3: Implement the engine (flat part)**

```python
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
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/unit/test_engine.py -v`
Expected: 4 PASSED

- [ ] **Step 5: Commit**

```bash
git add src/setup_doctor/engine.py tests/unit/test_engine.py
git commit -m "feat: diagnosis engine flat mode with summary and exit codes"
```

---

## Task 12: Diagnosis Engine — dep mode (DAG + root cause)

**Files:**
- Modify: `src/setup_doctor/engine.py` (add `_build_dag_diagnosis` etc.)
- Modify: `tests/unit/test_engine.py` (add dep tests)

- [ ] **Step 1: Write the failing test**

```python
# append to tests/unit/test_engine.py
def test_dep_groups_root_cause():
    checks = [
        CheckResult("sdk", "SDK", "node", status=CheckStatus.FAIL, depends_on=[]),
        CheckResult("deps", "Deps", "node", status=CheckStatus.FAIL, depends_on=["sdk"]),
        CheckResult("build", "Build", "node", status=CheckStatus.FAIL, depends_on=["deps"]),
        CheckResult("lock", "Lock", "node", status=CheckStatus.PASS),
    ]
    report = diagnose(checks, "dep", "/repo", "windows")
    assert report.diagnosis is not None
    rcs = report.diagnosis.root_causes
    assert len(rcs) == 1
    assert rcs[0].cause_check_id == "sdk"
    assert set(rcs[0].affected_checks) == {"sdk", "deps", "build"}
    assert rcs[0].chain == "sdk → deps → build"
    assert checks[1].caused_by == "sdk"
    assert checks[2].caused_by == "sdk"
    assert checks[0].caused_by is None


def test_dep_two_independent_roots():
    checks = [
        CheckResult("a", "A", "node", status=CheckStatus.FAIL, depends_on=[]),
        CheckResult("b", "B", "node", status=CheckStatus.FAIL, depends_on=[]),
    ]
    report = diagnose(checks, "dep", "/repo", "windows")
    assert len(report.diagnosis.root_causes) == 2


def test_dep_mixed_pass_fail_no_caused_by_on_pass():
    checks = [
        CheckResult("a", "A", "node", status=CheckStatus.FAIL, depends_on=[]),
        CheckResult("b", "B", "node", status=CheckStatus.PASS, depends_on=["a"]),
    ]
    report = diagnose(checks, "dep", "/repo", "windows")
    assert checks[1].caused_by is None
    assert len(report.diagnosis.root_causes) == 1
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/unit/test_engine.py -k dep -v`
Expected: FAIL (`diagnosis` is `None` in dep mode yet, or wrong grouping)

- [ ] **Step 3: Implement the DAG logic**

Append to `src/setup_doctor/engine.py`:

```python
def _find_root(by_id: dict[str, CheckResult], check_id: str, failed_ids: set[str], seen: set[str]) -> str:
    if check_id in seen:
        return check_id
    seen.add(check_id)
    failed_deps = [d for d in by_id[check_id].depends_on if d in failed_ids]
    if not failed_deps:
        return check_id
    return _find_root(by_id, failed_deps[0], failed_ids, seen)


def _downstream(by_id: dict[str, CheckResult], node_id: str, failed_ids: set[str], root_id: str) -> str | None:
    """Return the first failed check that depends (directly) on node_id and is caused by root_id."""
    for c in by_id.values():
        if (c.check_id in failed_ids and c.check_id != root_id
                and node_id in c.depends_on and c.caused_by == root_id):
            return c.check_id
    return None


def _build_dag_diagnosis(checks: list[CheckResult]) -> Diagnosis:
    by_id = {c.check_id: c for c in checks}
    failed_ids = {c.check_id for c in checks if c.status == CheckStatus.FAIL}
    for c in checks:
        if c.check_id in failed_ids:
            root = _find_root(by_id, c.check_id, failed_ids, set())
            if root != c.check_id:
                c.caused_by = root
    roots = sorted(c.check_id for c in checks if c.check_id in failed_ids and c.caused_by is None)
    root_causes: list[RootCause] = []
    for root_id in roots:
        affected = sorted(c.check_id for c in checks if c.caused_by == root_id)
        chain_nodes = [root_id]
        current = root_id
        while True:
            nxt = _downstream(by_id, current, failed_ids, root_id)
            if nxt is None:
                break
            chain_nodes.append(nxt)
            current = nxt
        root_causes.append(RootCause(
            cause_check_id=root_id,
            message=f"{by_id[root_id].name} is a root cause of {len(affected)} failing check(s)",
            affected_checks=[root_id] + affected,
            chain=" → ".join(chain_nodes),
        ))
    return Diagnosis(root_causes=root_causes)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/unit/test_engine.py -v`
Expected: 7 PASSED

- [ ] **Step 5: Commit**

```bash
git add src/setup_doctor/engine.py tests/unit/test_engine.py
git commit -m "feat: dep mode - DAG root-cause grouping and caused_by marking"
```

---

## Task 13: Output (text/JSON) + snapshot tests

**Files:**
- Create: `src/setup_doctor/output.py`
- Create: `tests/unit/test_output.py`
- Create: `tests/snapshots/report_basic.json`

- [ ] **Step 1: Write the failing test + golden file**

```python
# tests/unit/test_output.py
import json
from pathlib import Path
from setup_doctor.output import render_text, render_json
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
```

`tests/snapshots/report_basic.json` (golden file):

```json
{
  "schema_version": "1.0",
  "repo_path": "/repo",
  "os": "windows",
  "mode": "dep",
  "summary": {"total": 2, "pass": 0, "fail": 2, "skip": 0, "warnings": 0},
  "checks": [
    {
      "check_id": "sdk",
      "name": "SDK",
      "ecosystem": "node",
      "severity": "error",
      "status": "fail",
      "evidence": "node v18 expected >=20",
      "remediation": [{"step": "Install node 22", "command": "nvm install 22", "safe_fix": false, "source": "manual", "files": []}],
      "depends_on": ["runtime"],
      "caused_by": null
    },
    {
      "check_id": "deps",
      "name": "Deps",
      "ecosystem": "node",
      "severity": "error",
      "status": "fail",
      "evidence": "missing",
      "remediation": [],
      "depends_on": ["sdk"],
      "caused_by": "sdk"
    }
  ],
  "diagnosis": {
    "root_causes": [
      {
        "cause_check_id": "sdk",
        "message": "SDK is a root cause of 1 failing check(s)",
        "affected_checks": ["sdk", "deps"],
        "chain": "sdk → deps"
      }
    ],
    "ai_explanation": null
  },
  "exit_code": 1
}
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/unit/test_output.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'setup_doctor.output'`

- [ ] **Step 3: Implement the output module**

```python
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
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/unit/test_output.py -v`
Expected: 2 PASSED

- [ ] **Step 5: Commit**

```bash
git add src/setup_doctor/output.py tests/unit/test_output.py tests/snapshots/report_basic.json
git commit -m "feat: output renderers (text/json) with JSON snapshot test"
```

---

## Task 14: Fixer (--fix with backup, apply, rollback)

**Files:**
- Create: `src/setup_doctor/fixer.py`
- Create: `tests/integration/test_fixer.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/integration/test_fixer.py
import os
import pytest
from setup_doctor.fixer import Fixer
from setup_doctor.models import Report, CheckResult, CheckStatus, RemediationStep
from setup_doctor.utils.commands import CommandResult


def _report_with_fixables():
    checks = [
        CheckResult("env", "env", "services", status=CheckStatus.FAIL,
                    remediation=[RemediationStep("Create .env", "copy .env.example .env",
                                                 safe_fix=True, files=[".env"])]),
        CheckResult("deps", "deps", "node", status=CheckStatus.FAIL,
                    remediation=[RemediationStep("ci", "npm ci", safe_fix=True)]),
        CheckResult("sdk", "sdk", "node", status=CheckStatus.FAIL,
                    remediation=[RemediationStep("install", "nvm install 22", safe_fix=False)]),  # not safe
    ]
    return Report(repo_path="", os="windows", summary={}, checks=checks)


def test_fixer_applies_safe_manual_and_backs_up(fake_runner, monkeypatch, tmp_path):
    (tmp_path / ".env.example").write_text("KEY=value\n", encoding="utf-8")
    (tmp_path / ".env").write_text("OLD=1\n", encoding="utf-8")
    fake_runner.set(["copy", ".env.example", ".env"], CommandResult(0, "", ""))
    fake_runner.set(["npm", "ci"], CommandResult(0, "", ""))
    monkeypatch.setattr("setup_doctor.fixer.run_command", fake_runner)

    report = _report_with_fixables()
    report.repo_path = str(tmp_path)
    fix = Fixer(str(tmp_path)).apply(report)

    statuses = {e.status for e in fix.entries}
    assert "applied" in statuses          # .env + npm ci
    assert "skipped" in statuses          # nvm (not safe)
    assert (tmp_path / ".env").read_text(encoding="utf-8") == "KEY=value\n"
    backup_dir = os.path.join(str(tmp_path), ".setup-doctor-backup")
    assert os.path.isdir(backup_dir)
    backups = [d for d in os.listdir(backup_dir)]
    assert len(backups) == 1


def test_fixer_rolls_back_on_failure(fake_runner, monkeypatch, tmp_path):
    (tmp_path / ".env").write_text("OLD=1\n", encoding="utf-8")
    fake_runner.set(["copy", ".env.example", ".env"], CommandResult(1, "", "boom"))
    monkeypatch.setattr("setup_doctor.fixer.run_command", fake_runner)

    report = _report_with_fixables()
    report.checks = [c for c in report.checks if c.check_id == "env"]
    report.repo_path = str(tmp_path)
    fix = Fixer(str(tmp_path)).apply(report)

    assert fix.entries[0].status == "failed"
    assert (tmp_path / ".env").read_text(encoding="utf-8") == "OLD=1\n"  # restored
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/integration/test_fixer.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'setup_doctor.fixer'`

- [ ] **Step 3: Implement the Fixer**

```python
# src/setup_doctor/fixer.py
from __future__ import annotations
import datetime
import os
import shutil
from dataclasses import dataclass, field
from .models import Report
from .utils.commands import run_command


@dataclass
class FixLogEntry:
    command: str
    status: str  # applied | skipped | failed
    detail: str = ""


@dataclass
class FixReport:
    backup_dir: str
    entries: list[FixLogEntry] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "backup_dir": self.backup_dir,
            "entries": [{"command": e.command, "status": e.status, "detail": e.detail}
                        for e in self.entries],
        }


class Fixer:
    BACKUP_DIR_NAME = ".setup-doctor-backup"

    def __init__(self, repo_path: str):
        self.repo_path = repo_path
        stamp = datetime.datetime.now().strftime("%Y%m%d-%H%M%S")
        self.backup_dir = os.path.join(repo_path, self.BACKUP_DIR_NAME, stamp)

    def _backup_file(self, rel: str) -> None:
        src = os.path.join(self.repo_path, rel)
        if not os.path.exists(src):
            return
        dst = os.path.join(self.backup_dir, rel)
        os.makedirs(os.path.dirname(dst), exist_ok=True)
        shutil.copy2(src, dst)

    def _restore_file(self, rel: str) -> None:
        dst = os.path.join(self.backup_dir, rel)
        if os.path.exists(dst):
            shutil.copy2(dst, os.path.join(self.repo_path, rel))

    def _apply_step(self, step, entry: FixLogEntry) -> None:
        saved = list(step.files)
        for rel in step.files:
            self._backup_file(rel)
        res = run_command(step.command.split("&&") if False else _split_command(step.command),
                          cwd=self.repo_path, timeout=120)
        if res.ok:
            entry.status = "applied"
        else:
            entry.status = "failed"
            entry.detail = res.stderr
            for rel in saved:
                self._restore_file(rel)

    def apply(self, report: Report) -> FixReport:
        os.makedirs(self.backup_dir, exist_ok=True)
        fix_report = FixReport(backup_dir=self.backup_dir)
        for c in report.checks:
            if c.status.value != "fail":
                continue
            for step in c.remediation:
                entry = FixLogEntry(command=step.command, status="skipped")
                if not step.safe_fix or step.source != "manual":
                    entry.detail = "not safe_fix or not manual"
                else:
                    self._apply_step(step, entry)
                fix_report.entries.append(entry)
        return fix_report


def _split_command(command: str) -> list[str]:
    """Split a command string into argv, honoring double quotes."""
    import shlex
    return shlex.split(command, posix=False) if os.name == "nt" else shlex.split(command)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/integration/test_fixer.py -v`
Expected: 2 PASSED

- [ ] **Step 5: Commit**

```bash
git add src/setup_doctor/fixer.py tests/integration/test_fixer.py
git commit -m "feat: fixer applies safe manual remediations with backup + rollback"
```

---

## Task 15: AI provider (interface + OpenAI/Anthropic + FakeProvider)

**Files:**
- Create: `src/setup_doctor/ai/__init__.py`
- Create: `src/setup_doctor/ai/provider.py`
- Create: `tests/unit/test_ai.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/unit/test_ai.py
import os
import pytest
from setup_doctor.ai.provider import AIProvider, AIUnavailableError, get_provider
from setup_doctor.config import AIConfig, ToolConfig


def test_get_provider_requires_key(monkeypatch):
    monkeypatch.delenv("SETUP_DOCTOR_API_KEY", raising=False)
    with pytest.raises(AIUnavailableError):
        get_provider(ToolConfig())


def test_get_provider_returns_openai_client(monkeypatch):
    monkeypatch.setenv("SETUP_DOCTOR_API_KEY", "sk-test")
    cfg = ToolConfig(ai=AIConfig(provider="openai"))
    provider = get_provider(cfg)
    from setup_doctor.ai.provider import OpenAIClient
    assert isinstance(provider, OpenAIClient)
    assert provider.model == "gpt-4o-mini"


def test_fake_provider_contract():
    class FakeProvider(AIProvider):
        def __init__(self, data):
            self.data = data
        def complete(self, system, user, response_schema):
            return self.data

    fp = FakeProvider({"suggestions": []})
    assert fp.complete("s", "u", dict) == {"suggestions": []}
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/unit/test_ai.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'setup_doctor.ai'`

- [ ] **Step 3: Implement the provider**

```python
# src/setup_doctor/ai/__init__.py
"""Optional AI enhancement layer. Never required for core diagnosis."""
```

```python
# src/setup_doctor/ai/provider.py
from __future__ import annotations
import json
import os
from ..config import ToolConfig


class AIUnavailableError(Exception):
    """Raised when the LLM cannot be reached or has no API key."""


class AIProvider:
    def complete(self, system: str, user: str, response_schema: type) -> dict | None:
        raise NotImplementedError


class OpenAIClient(AIProvider):
    def __init__(self, api_key: str, model: str = "gpt-4o-mini", timeout_sec: int = 20):
        self._api_key = api_key
        self.model = model
        self._timeout_sec = timeout_sec

    def complete(self, system: str, user: str, response_schema: type) -> dict | None:
        try:
            from openai import OpenAI
        except ImportError as exc:
            raise AIUnavailableError("openai package not installed (pip install setup-doctor[ai])") from exc
        try:
            client = OpenAI(api_key=self._api_key, timeout=self._timeout_sec)
            resp = client.chat.completions.create(
                model=self.model,
                messages=[{"role": "system", "content": system},
                          {"role": "user", "content": user}],
                response_format={"type": "json_object"},
            )
            return json.loads(resp.choices[0].message.content)
        except Exception as exc:  # network, auth, rate limit, malformed JSON
            raise AIUnavailableError(str(exc)) from exc


class AnthropicClient(AIProvider):
    def __init__(self, api_key: str, model: str = "claude-3-5-haiku-latest", timeout_sec: int = 20):
        self._api_key = api_key
        self.model = model
        self._timeout_sec = timeout_sec

    def complete(self, system: str, user: str, response_schema: type) -> dict | None:
        try:
            from anthropic import Anthropic
        except ImportError as exc:
            raise AIUnavailableError("anthropic package not installed (pip install setup-doctor[ai])") from exc
        try:
            client = Anthropic(api_key=self._api_key, timeout=self._timeout_sec)
            resp = client.messages.create(
                model=self.model,
                max_tokens=500,
                system=system,
                messages=[{"role": "user", "content": user}],
            )
            return json.loads(resp.content[0].text)
        except Exception as exc:
            raise AIUnavailableError(str(exc)) from exc


def get_provider(cfg: ToolConfig, api_key: str | None = None) -> AIProvider:
    api_key = api_key or os.environ.get("SETUP_DOCTOR_API_KEY")
    if not api_key:
        raise AIUnavailableError("Missing API key; set SETUP_DOCTOR_API_KEY")
    if cfg.ai.provider == "anthropic":
        return AnthropicClient(api_key, model=cfg.ai.model, timeout_sec=cfg.ai.timeout_sec)
    return OpenAIClient(api_key, model=cfg.ai.model, timeout_sec=cfg.ai.timeout_sec)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/unit/test_ai.py -v`
Expected: 3 PASSED

- [ ] **Step 5: Commit**

```bash
git add src/setup_doctor/ai tests/unit/test_ai.py
git commit -m "feat: AI provider interface with OpenAI/Anthropic clients and key handling"
```

---

## Task 16: AI remediation + explainer (with fallback)

**Files:**
- Create: `src/setup_doctor/ai/remediation.py`
- Create: `src/setup_doctor/ai/explainer.py`
- Modify: `tests/unit/test_ai.py` (add remediation/explainer tests)

- [ ] **Step 1: Write the failing test**

```python
# append to tests/unit/test_ai.py
from setup_doctor.ai.provider import AIProvider, AIUnavailableError
from setup_doctor.ai.remediation import AIRemediation
from setup_doctor.ai.explainer import AIExplainer
from setup_doctor.models import CheckResult, CheckStatus, RemediationStep, Diagnosis, RootCause


class FakeProvider(AIProvider):
    def __init__(self, data, error=False):
        self.data = data
        self.error = error
    def complete(self, system, user, response_schema):
        if self.error:
            raise AIUnavailableError("offline")
        return self.data


def test_ai_remediation_appends_suggestions_after_manual():
    manual = [RemediationStep("Install Node", "nvm install 22", safe_fix=False)]
    cr = CheckResult("sdk", "SDK", "node", status=CheckStatus.FAIL, evidence="18 < 20",
                     remediation=manual)
    provider = FakeProvider({"suggestions": [{"step": "Upgrade node", "command": "nvm install 20"}]})
    steps = AIRemediation(provider).suggest(cr, "windows")
    assert steps[0].command == "nvm install 22"      # manual first
    assert steps[-1].source == "ai"
    assert steps[-1].safe_fix is False


def test_ai_remediation_falls_back_on_error():
    cr = CheckResult("sdk", "SDK", "node", status=CheckStatus.FAIL, evidence="18 < 20",
                     remediation=[RemediationStep("Install Node", "nvm install 22")])
    steps = AIRemediation(FakeProvider(None, error=True)).suggest(cr, "windows")
    assert len(steps) == 1
    assert steps[0].command == "nvm install 22"


def test_ai_explainer_returns_text():
    diag = Diagnosis(root_causes=[RootCause("sdk", "msg", ["a"], "a → b")])
    provider = FakeProvider({"explanation": "Vì SDK thiếu nên deps không cài được."})
    assert AIExplainer(provider).explain(diag) == "Vì SDK thiếu nên deps không cài được."


def test_ai_explainer_none_on_error():
    diag = Diagnosis(root_causes=[RootCause("sdk", "msg", ["a"], "a → b")])
    assert AIExplainer(FakeProvider(None, error=True)).explain(diag) is None
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/unit/test_ai.py -v`
Expected: FAIL (`ModuleNotFoundError: No module named 'setup_doctor.ai.remediation'`)

- [ ] **Step 3: Implement remediation + explainer**

```python
# src/setup_doctor/ai/remediation.py
from __future__ import annotations
from ..models import CheckResult, RemediationStep

_SYSTEM_PROMPT = (
    "You are a developer-environment troubleshooting assistant. "
    "Given a failing setup check, suggest 1-3 concrete fix commands for the given OS. "
    'Reply with JSON only: {"suggestions": [{"step": "...", "command": "..."}]}. '
    "Commands must be copy-pasteable and specific."
)


class AIRemediation:
    def __init__(self, provider, max_requests: int = 10):
        self._provider = provider
        self._remaining = max_requests

    def suggest(self, check: CheckResult, os_name: str) -> list[RemediationStep]:
        manual = list(check.remediation)
        if self._remaining <= 0:
            return manual
        self._remaining -= 1
        user = (f"OS: {os_name}\ncheck_id: {check.check_id}\n"
                f"evidence: {check.evidence}\n")
        try:
            data = self._provider.complete(_SYSTEM_PROMPT, user, dict)
        except Exception:
            return manual
        if not data or not isinstance(data, dict):
            return manual
        for item in data.get("suggestions", []):
            manual.append(RemediationStep(
                step=str(item.get("step", "")),
                command=str(item.get("command", "")),
                safe_fix=False,
                source="ai",
            ))
        return manual
```

```python
# src/setup_doctor/ai/explainer.py
from __future__ import annotations
from ..models import Diagnosis

_SYSTEM_PROMPT = (
    "You explain developer setup failures concisely. "
    'Reply with JSON only: {"explanation": "..."} — max 3 sentences. '
    "Explain the root cause first, then what breaks downstream."
)


class AIExplainer:
    def __init__(self, provider):
        self._provider = provider

    def explain(self, diagnosis: Diagnosis | None) -> str | None:
        if not diagnosis or not diagnosis.root_causes:
            return None
        chains = "; ".join(rc.chain for rc in diagnosis.root_causes)
        messages = "; ".join(rc.message for rc in diagnosis.root_causes)
        user = f"Root cause chains: {chains}\nMessages: {messages}"
        try:
            data = self._provider.complete(_SYSTEM_PROMPT, user, dict)
        except Exception:
            return None
        if not data or not isinstance(data, dict):
            return None
        return data.get("explanation")
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/unit/test_ai.py -v`
Expected: 7 PASSED

- [ ] **Step 5: Commit**

```bash
git add src/setup_doctor/ai/remediation.py src/setup_doctor/ai/explainer.py tests/unit/test_ai.py
git commit -m "feat: AI remediation suggestions and root-cause explainer with rule-based fallback"
```

---

## Task 17: Study harness (metrics + runner)

**Files:**
- Create: `src/setup_doctor/study/__init__.py`
- Create: `src/setup_doctor/study/metrics.py`
- Create: `src/setup_doctor/study/runner.py`
- Create: `tests/unit/test_metrics.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/unit/test_metrics.py
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
    gt = {"expected_failures": ["a", "b"]}
    m = compute_metrics(_report(), gt)
    assert m["tp"] == 2
    assert m["fp"] == 0
    assert m["fn"] == 0
    assert m["precision"] == 1.0
    assert m["recall"] == 1.0
    assert m["f1"] == 1.0


def test_metrics_recall_partial():
    gt = {"expected_failures": ["a", "b", "zz"]}
    m = compute_metrics(_report(), gt)
    assert m["recall"] == 2 / 3
    assert m["fn"] == 1


def test_metrics_clarity_dep_mode():
    gt = {"expected_failures": ["a", "b"], "expected_root_causes": ["a"]}
    m = compute_metrics(_report(mode="dep"), gt)
    assert m["clarity"] == 1.0


def test_metrics_clarity_zero_when_none_expected():
    gt = {"expected_failures": ["a", "b"], "expected_root_causes": []}
    m = compute_metrics(_report(mode="dep"), gt)
    assert m["clarity"] == 0.0
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/unit/test_metrics.py -v`
Expected: FAIL (`ModuleNotFoundError: No module named 'setup_doctor.study'`)

- [ ] **Step 3: Implement metrics + runner**

```python
# src/setup_doctor/study/__init__.py
"""Research harness: repeatable cross-repo flat-vs-dep comparison."""
```

```python
# src/setup_doctor/study/metrics.py
from __future__ import annotations
from ..models import Report, CheckStatus


def compute_metrics(report: Report, ground_truth: dict) -> dict:
    expected = set(ground_truth.get("expected_failures", []))
    predicted = {c.check_id for c in report.checks if c.status == CheckStatus.FAIL}
    tp = len(predicted & expected)
    fp = len(predicted - expected)
    fn = len(expected - predicted)
    # accuracy over all checks the tool performed
    total = len(report.checks)
    tn = total - len(predicted | expected)
    precision = tp / (tp + fp) if (tp + fp) else 0.0
    recall = tp / (tp + fn) if (tp + fn) else 0.0
    f1 = 2 * precision * recall / (precision + recall) if (precision + recall) else 0.0
    accuracy = (tp + tn) / total if total else 0.0

    clarity = 0.0
    if report.diagnosis is not None:
        expected_rc = set(ground_truth.get("expected_root_causes", []))
        rc_ids = {rc.cause_check_id for rc in report.diagnosis.root_causes}
        clarity = len(rc_ids & expected_rc) / len(expected_rc) if expected_rc else 0.0

    return {
        "total": total, "tp": tp, "fp": fp, "fn": fn, "tn": tn,
        "precision": round(precision, 4),
        "recall": round(recall, 4),
        "f1": round(f1, 4),
        "accuracy": round(accuracy, 4),
        "clarity": round(clarity, 4),
        "predicted": sorted(predicted),
        "expected": sorted(expected),
    }
```

```python
# src/setup_doctor/study/runner.py
from __future__ import annotations
import csv
import json
import os
from pathlib import Path
from ..engine import diagnose
from ..registry import detect_ecosystems, get_checkers
from ..context import CheckContext
from ..utils.osdetect import detect_os
from .metrics import compute_metrics


def _ground_truth_map(path: str) -> dict[str, dict]:
    result: dict[str, dict] = {}
    if not path:
        return result
    p = Path(path)
    if p.is_dir():
        for f in sorted(p.glob("*.json")):
            data = json.loads(f.read_text(encoding="utf-8"))
            result[data["repo"]] = data
    else:
        data = json.loads(Path(path).read_text(encoding="utf-8"))
        result[data["repo"]] = data
    return result


def run_study(repos_file: str, ground_truth_path: str | None, output_dir: str) -> str:
    repos = [line.strip() for line in open(repos_file, encoding="utf-8") if line.strip()]
    gt = _ground_truth_map(ground_truth_path) if ground_truth_path else {}
    os.makedirs(output_dir, exist_ok=True)
    rows: list[dict] = []
    os_name = detect_os()
    for repo in repos:
        gt_entry = gt.get(repo, {})
        ecosystems = detect_ecosystems(repo)
        checkers = get_checkers(ecosystems | {"registry"} if ecosystems else set())
        checks = []
        if checkers:
            ctx = CheckContext(repo_path=repo, os=os_name)
            for checker in checkers:
                checks.extend(checker.run(ctx))
        for mode in ("flat", "dep"):
            report = diagnose(checks, mode, repo, os_name)
            metrics = compute_metrics(report, gt_entry)
            rows.append({"repo": repo, "mode": mode, **metrics})
    # write outputs
    csv_path = os.path.join(output_dir, "study_results.csv")
    with open(csv_path, "w", newline="", encoding="utf-8") as f:
        fieldnames = list(rows[0].keys()) if rows else ["repo", "mode"]
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)
    json_path = os.path.join(output_dir, "study_results.json")
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(rows, f, indent=2, ensure_ascii=False)
    return csv_path
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/unit/test_metrics.py -v`
Expected: 4 PASSED

- [ ] **Step 5: Commit**

```bash
git add src/setup_doctor/study tests/unit/test_metrics.py
git commit -m "feat: study harness metrics (precision/recall/accuracy/clarity/f1) and CSV/JSON runner"
```

---

## Task 18: Runner + CLI + E2E test + README

**Files:**
- Create: `src/setup_doctor/runner.py`
- Create: `src/setup_doctor/cli.py`
- Create: `tests/integration/test_cli.py`
- Create: `README.md` (replace placeholder)

- [ ] **Step 1: Write the failing E2E test**

```python
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


def test_cli_check_json_ok(fake_runner, monkeypatch, tmp_path):
    write_json(tmp_path / "package.json", {"engines": {"node": ">=18.0.0"}})
    (tmp_path / "package-lock.json").write_text("{}", encoding="utf-8")
    (tmp_path / "node_modules").mkdir()
    fake_runner.set(["node", "--version"], __import__("setup_doctor.utils.commands", fromlist=["CommandResult"]).CommandResult(0, "v22.0.0", ""))
    monkeypatch.setattr("setup_doctor.checkers.node.which", lambda name: "C:\\node\\node.exe" if name == "node" else ("C:\\node\\npm.cmd" if name == "npm" else None))
    monkeypatch.setattr("setup_doctor.checkers.node.run_command", fake_runner)
    # -m setup_doctor.cli runs in a subprocess, so monkeypatch won't apply;
    # instead, invoke main() in-process for the node scenario.
    from setup_doctor.cli import main
    rc = main(["check", str(tmp_path), "--format", "json"])
    assert rc == 0
```

Note on testing strategy: subprocess E2E (`test_cli_check_json_ok`) patches won't propagate into a child process, so the node-check scenario is tested **in-process** via `main([...])` with monkeypatched command utils, while pure-IO subprocess tests (`--version`, no-ecosystem) run as real processes. `cli.main` must return the exit code.

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/integration/test_cli.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'setup_doctor.cli'`

- [ ] **Step 3: Implement runner + CLI**

```python
# src/setup_doctor/runner.py
from __future__ import annotations
from .config import ToolConfig
from .context import CheckContext
from .engine import diagnose
from .models import Report
from .registry import detect_ecosystems, get_checkers
from .utils.osdetect import detect_os


class NoEcosystemError(Exception):
    def __init__(self, repo_path: str):
        super().__init__(repo_path)
        self.repo_path = repo_path


def run_check(repo_path: str, mode: str, config: ToolConfig, ai_enabled: bool = False) -> Report:
    os_name = detect_os()
    ecosystems = detect_ecosystems(repo_path)
    if not ecosystems:
        raise NoEcosystemError(repo_path)
    ctx = CheckContext(repo_path=repo_path, os=os_name, config=config)
    checks = []
    for checker in get_checkers(ecosystems | {"registry"} if "registry" not in ecosystems else ecosystems):
        checks.extend(checker.run(ctx))
    report = diagnose(checks, mode, repo_path, os_name)
    if ai_enabled:
        _enhance_with_ai(report, config)
    return report


def _enhance_with_ai(report: Report, config: ToolConfig) -> None:
    from .ai.provider import get_provider, AIUnavailableError
    from .ai.remediation import AIRemediation
    from .ai.explainer import AIExplainer
    try:
        provider = get_provider(config)
    except AIUnavailableError:
        return  # fallback: keep rule-based content only
    remediator = AIRemediation(provider, max_requests=config.ai.max_requests)
    for c in report.checks:
        if c.status.value == "fail":
            c.remediation = remediator.suggest(c, report.os)
    if report.diagnosis is not None:
        report.diagnosis.ai_explanation = AIExplainer(provider).explain(report.diagnosis)
```

```python
# src/setup_doctor/cli.py
from __future__ import annotations
import argparse
import sys
from . import __version__
from .config import load_config
from .output import render_text, render_json
from .runner import run_check, NoEcosystemError
from .fixer import Fixer
from .study.runner import run_study


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="setup-doctor")
    parser.add_argument("--version", action="version", version=f"setup-doctor {__version__}")
    sub = parser.add_subparsers(dest="command", required=True)

    check_p = sub.add_parser("check", help="diagnose one repository")
    check_p.add_argument("repo_path")
    check_p.add_argument("--mode", choices=["flat", "dep"], help="default from config")
    check_p.add_argument("--format", choices=["text", "json"], help="default from config")
    check_p.add_argument("--output", help="write JSON output to file (json only)")
    check_p.add_argument("--fix", action="store_true", help="apply safe remediations with backup")
    check_p.add_argument("--ai", action="store_true", help="enhance remediation/explanation with LLM")
    check_p.add_argument("--config", help="path to setup-doctor.toml")
    check_p.add_argument("--verbose", action="store_true")

    study_p = sub.add_parser("study", help="run repeatable flat-vs-dep research")
    study_p.add_argument("repos_file")
    study_p.add_argument("--ground-truth", help="JSON file or dir of ground-truth files")
    study_p.add_argument("--output-dir", default="research/output")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _build_parser().parse_args(argv)
    try:
        if args.command == "check":
            return _cmd_check(args)
        if args.command == "study":
            run_study(args.repos_file, args.ground_truth, args.output_dir)
            return 0
    except NoEcosystemError as exc:
        print(f"no supported ecosystem detected for {exc.repo_path}", file=sys.stdout)
        return 0
    except KeyboardInterrupt:
        return 130
    except Exception as exc:  # internal tool error -> exit 2
        print(f"setup-doctor: internal error: {exc}", file=sys.stderr)
        if getattr(args, "verbose", False):
            import traceback
            traceback.print_exc()
        return 2
    return 2


def _cmd_check(args) -> int:
    config = load_config(path=args.config, overrides={
        "mode": args.mode,
        "format": args.format,
        "ai": args.ai,
    })
    mode = args.mode or config.default_mode
    report = run_check(args.repo_path, mode, config, ai_enabled=args.ai)
    if args.format == "json" or config.output_format == "json":
        payload = render_json(report)
        if args.output:
            with open(args.output, "w", encoding="utf-8") as f:
                f.write(payload)
        else:
            print(payload)
    else:
        print(render_text(report))
    if args.fix:
        fix = Fixer(args.repo_path).apply(report)
        if args.verbose:
            for e in fix.entries:
                print(f"fix: {e.status} -> {e.command} {e.detail}")
    return report.exit_code


if __name__ == "__main__":
    sys.exit(main())
```

- [ ] **Step 4: Run all tests**

Run: `python -m pytest -v`
Expected: ALL PASS (command tests + engine + checkers + output + fixer + ai + metrics)

- [ ] **Step 5: Manual smoke test**

Run: `python -m setup_doctor.cli check <path-to-tmp-node-repo> --format json`
Expected: JSON report printed, exit 0 if repo healthy / 1 if failing checks are error-severity.

- [ ] **Step 6: Write README**

`README.md` (replacing the placeholder):

```markdown
# Developer Setup Doctor

CLI chẩn đoán môi trường thiết lập cho một repository: SDK, dependencies, dịch vụ cục bộ,
kèm bước khắc phục chính xác và kết quả machine-readable (JSON + exit code).

## Cài đặt

```bash
pip install -e ".[dev]"        # phát triển
pip install -e ".[ai]"         # thêm hỗ trợ AI (openai/anthropic)
```

## Sử dụng

```bash
setup-doctor check <repo>                  # chẩn đoán (mặc định mode=dep, text)
setup-doctor check <repo> --mode flat      # checklist phẳng
setup-doctor check <repo> --format json    # JSON machine-readable
setup-doctor check <repo> --fix            # áp dụng remediation an toàn (có backup)
setup-doctor check <repo> --ai             # tăng cường AI (cần SETUP_DOCTOR_API_KEY)
setup-doctor study repos.txt --ground-truth research/ground_truth --output-dir research/output
setup-doctor --version
```

Exit codes: `0` pass/không-ecosystem, `1` có lỗi, `2` lỗi nội bộ.

## Cấu hình

`setup-doctor.toml` (xem spec section 4.8). Ưu tiên: `CLI > env (SETUP_DOCTOR_*) > file > default`.

## An toàn

- Mặc định `read-only`: chạy check không thay đổi repo.
- `--fix` chỉ áp dụng các remediation `safe_fix` + `source=manual`, backup vào
  `.setup-doctor-backup/<ts>/`, log mọi thay đổi, rollback khi lệnh lỗi.
- AI chỉ gửi `check_id`/evidence đã lọc/OS; key đọc từ env; nghiên cứu (`study`) luôn
  chạy rule-based (deterministic).

## Nghiên cứu

`setup-doctor study` so sánh hai mode (flat vs dep) theo precision/recall/accuracy/clarity/f1.
Chi tiết spec: `docs/superpowers/specs/2026-09-15-developer-setup-doctor-design.md`.
```

- [ ] **Step 7: Commit**

```bash
git add src/setup_doctor/runner.py src/setup_doctor/cli.py tests/integration/test_cli.py README.md
git commit -m "feat: runner + CLI (check/study) with exit codes, README"
```

---

## Self-Review Checklist (run after writing — verify against spec)

**Spec coverage:**
- FR-1 (ecosystem detect) → Task 4 ✅
- FR-2 (SDK version) → Tasks 5-8 ✅
- FR-3 (deps) → Tasks 5, 6, 7, 8 ✅
- FR-4 (services) → Task 9 ✅
- FR-5 (registry/credentials, không đọc nội dung) → Task 10 ✅
- FR-6 (2 modes cùng bộ check) → Tasks 11, 12 (engine nhận cùng `checks`) ✅
- FR-7 (JSON + exit codes) → Tasks 13, 18 ✅
- FR-8 (exact remediation steps) → mọi checker có `RemediationStep(step, command)` ✅
- FR-9 (--fix backup/log) → Task 14 ✅
- FR-10 (study) → Task 17 ✅
- FR-11 (không tự sửa khi không --fix) → checkers luôn read-only; fixer chỉ chạy khi `--fix` ✅
- FR-12/13 (AI remediation/explainer + fallback) → Tasks 15, 16 ✅
- FR-14 (study rule-based) → `run_study` không gọi AI ✅
- FR-15 (config file) → Task 3 ✅
- NFR-3 (timeout 30s) → `run_command` default timeout=30 ✅
- NFR-5 (OS-aware) → `detect_os` + commands theo OS ✅
- AC-1..AC-10 → các test tương ứng ✅

**Placeholder scan:** không có "TBD"/"TODO"; mọi bước đều có code đầy đủ.

**Type consistency:** `CheckResult(status=CheckStatus.X)` dùng enum nhất quán; `run_command` luôn trả `CommandResult`; `Fixer.apply(report) -> FixReport`; `main() -> int`; `compute_metrics(report, gt) -> dict` — khớp giữa các task.