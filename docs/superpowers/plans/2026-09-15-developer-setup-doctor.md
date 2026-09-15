# Developer Setup Doctor Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build `setup-doctor`, a Python CLI that diagnoses one repository's SDK, dependencies, and local-service prerequisites, prints exact remediation steps, emits machine-readable JSON + exit codes, compares flat vs dependency-aware diagnosis modes, and runs a repeatable research harness — with optional AI-enhanced remediation/explanation that stays isolated from research.

**Architecture:** Plugin-style checker framework in Python 3.11+. Each ecosystem (node, python, java, dotnet, services, registry) is one read-only `Checker` class returning normalized `CheckResult` objects. A `DiagnosisEngine` consumes the same check results in two modes: `flat` (plain checklist) and `dep` (builds a DAG from `depends_on`, groups failures by root cause). Output layer renders text/JSON and computes exit codes. A `Fixer` applies only whitelisted `safe_fix` remediations with transactional backup + log + rollback. AI is an optional enhancement layer (`--ai`) with a provider interface and always-available rule-based fallback; the `study` harness is strictly rule-based/deterministic.

**Revision note (v1.2, sau review round 1):** plan đã được sửa theo review:
- Checkers **read-only**: không chạy `mvn dependency:resolve`/`dotnet restore`/build trong check; thay bằng kiểm tra static (cache dir, parse file). Các op tải deps chỉ ở `--fix`.
- ID check chuẩn hóa theo catalog spec 3.7: `*.deps.*`, `*.build.ready`, `*.restore.ready`, `*.deps.cached`...
- Registry: git user/SSH là **warning**; chỉ chạy khi repo có dấu hiệu cần; SSH skip khi remote HTTPS.
- Fixer thiết kế lại: whitelist op + transaction (backup toàn bộ, rollback toàn bộ, xóa file mới tạo, timestamp micro).
- Config: tự tìm file (cwd → repo root → home); `--ai` ba trạng thái None/True/False.
- AI: sanitize evidence, quota chung, validate schema.
- Metrics: accuracy trên universe nhãn; path không tồn tại → exit 2.

**Revision note (v1.3, sau review round 2):**
- Version parser: test `~20.4.0` đúng (loại 20.5.0); `>=18 || >=22` với 19.0.0 pass; `satisfies` trả `None` khi unsupported → checker báo **warning/skip**, không fail sai.
- DAG engine: `causes: list[str]` (mọi root causes) + `caused_by` (primary); `_failed_roots_of` xử lý multi-dep fail, skip-bridge, cycle, missing ID; có test cho từng edge case.
- Fixer: **hạ cam kết rollback** — whitelist op có `reversible` flag; npm ci/mvn/dotnet/docker là **non-reversible** (log rõ, không hứa khôi phục); bỏ xóa mọi path mới tạo nguy hiểm; chặn path traversal qua `_is_inside_repo`.
- Data model: tách `operation` + `argv` + `command`(display) trong `RemediationStep`; whitelist theo operation, không so khớp chuỗi hiển thị.
- Checker semantics: runtime có trong PATH nhưng `--version`/`--list-sdks` fail → FAIL; npm/docker thiếu (repo cần) → FAIL (không skip); `.venv` phải có `pyvenv.cfg`; deps fail khi thiếu venv (không pass giả); compose so container name theo prefix.
- Cache check: `.m2`/`.nuget` tồn tại → **warning** (không chứng minh deps repo sẵn sàng), thiếu → FAIL.
- Metrics: chốt quy tắc universe — ID trong ground truth LUÔN thuộc universe; tool không emit → FN; validate_ground_truth reject ID ngoài catalog; nêu rõ flat/dep KHÔNG khác nhau ở precision/recall (so sánh qua clarity + remediation_order thủ công).
- Nhỏ: entry-point registry có fallback import trực tiếp khi metadata rỗng; AC-9 chốt schema duy nhất (`ai_explanation` null/string); NFR-3 phân biệt timeout check (30s) vs fix op (timeout riêng); sửa số test count.

**Tech Stack:** Python ≥3.11, stdlib + PyYAML for core (`argparse`, `tomllib`, `dataclasses`, `subprocess`, `socket`), `pytest` for tests, optional `openai`/`anthropic` for AI, `setuptools` packaging with `pyproject.toml` + entry points (checker plugin registry).

**Spec:** `docs/superpowers/specs/2026-09-15-developer-setup-doctor-design.md` (v1.2)

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
src/setup_doctor/study/metrics.py       # compute_metrics trên universe (TP/FP/FN/TN)
src/setup_doctor/study/ground_truth.py  # validate_ground_truth: reject ID ngoài catalog
src/setup_doctor/study/runner.py        # run_study: chạy cả 2 mode, xuất CSV/JSON
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
    assert d["causes"] == []
    assert d["remediation"][0] == {
        "step": "Install Node 22",
        "command": "nvm install 22",
        "safe_fix": True,
        "source": "manual",
        "files": [],
        "operation": None,
        "argv": None,
    }


def test_remediation_step_with_operation_and_argv():
    step = RemediationStep("Install deps", "npm ci", safe_fix=True,
                           operation="install-node-deps", argv=["npm", "ci"])
    d = step.to_dict()
    assert d["operation"] == "install-node-deps"
    assert d["argv"] == ["npm", "ci"]


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
dependencies = ["PyYAML>=6.0"]

[project.optional-dependencies]
ai = ["openai>=1.0", "anthropic>=0.25"]
dev = ["pytest>=8.0"]

[project.scripts]
setup-doctor = "setup_doctor.cli:main"

# Plugin-style: checker đăng ký qua entry points (NFR-4).
# Thêm checker mới = thêm 1 module + 1 dòng entry point, không sửa registry.py.
[project.entry-points."setup_doctor.checkers"]
node = "setup_doctor.checkers.node:NodeChecker"
python = "setup_doctor.checkers.python_ck:PythonChecker"
java = "setup_doctor.checkers.java:JavaChecker"
dotnet = "setup_doctor.checkers.dotnet_ck:DotnetChecker"
services = "setup_doctor.checkers.services:ServicesChecker"
registry = "setup_doctor.checkers.registry:RegistryChecker"

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
    command: str = ""                    # display_command cho người dùng (vd "npm ci")
    safe_fix: bool = False
    source: str = "manual"
    files: list[str] = field(default_factory=list)  # repo-relative files để backup trước khi run
    operation: str | None = None         # whitelist op key ("install-node-deps", "create-env"...); None = chỉ hiển thị, KHÔNG tự fix
    argv: list[str] | None = None        # argv list cụ thể cho op (ưu tiên hơn command khi fix)

    def to_dict(self) -> dict:
        return {
            "step": self.step,
            "command": self.command,
            "safe_fix": self.safe_fix,
            "source": self.source,
            "files": list(self.files),
            "operation": self.operation,
            "argv": list(self.argv) if self.argv is not None else None,
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
    caused_by: str | None = None         # dep mode: primary root cause (first)
    causes: list[str] = field(default_factory=list)  # dep mode: TẤT CẢ root causes gây ra check này

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
            "causes": list(self.causes),
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
    assert satisfies("22.1.0", "^20.0.0")
    assert not satisfies("19.0.0", "^20.0.0")
    assert not satisfies("20.5.0", "~20.4.0")   # ~20.4.0 = >=20.4.0, <20.5.0 -> 20.5.0 KHÔNG thỏa
    assert satisfies("20.4.9", "~20.4.0")
    assert not satisfies("20.6.0", "~20.4.0")
    assert satisfies("18.0.0", "<20.0.0")
    assert not satisfies("20.0.0", "<20.0.0")
    assert satisfies("20.0.0", "<=20.0.0")
    assert satisfies("19.0.0", ">18.0.0")
    assert satisfies("22.1.0", ">=20 <23")          # khoảng: 20 <= v < 23
    assert not satisfies("23.1.0", ">=20 <23")
    assert satisfies("20.0.0", ">=18.0.0 || >=22.0.0")
    assert satisfies("19.0.0", ">=18.0.0 || >=22.0.0")  # 19 >= 18 -> thỏa vế trái


def test_satisfies_unsupported_constraint_returns_none():
    # constraint không hỗ trợ (vd "lts/*") -> trả None, KHÔNG fail sai
    assert satisfies("20.0.0", "lts/*") is None
    assert satisfies("20.0.0", "~dev") is None
    assert satisfies("", ">=20") is None          # không parse được version -> None


def test_parse_version_extracts_numbers():
    assert parse_version("Node.js v20.11.1") == (20, 11, 1)
    assert parse_version("") == ()


def test_parse_version_prerelease_ignored():
    assert parse_version("20.0.0-beta.1") == (20, 0, 0)
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


def satisfies(installed: str, constraint: str) -> bool | None:
    """Check an installed version string against a constraint.

    Hỗ trợ: ``>=X``, ``>X``, ``<X``, ``<=X``, ``^X`` (major-pinned),
    ``~X.Y.Z`` (patch-pinned), khoảng ``a b``, và ``a || b`` (OR).

    Trả về:
    - ``True``/``False`` nếu constraint hợp lệ.
    - ``None`` nếu **không xác định được** (constraint không hỗ trợ, hoặc
      version không parse được) — caller KHÔNG được coi là fail; phải báo
      ``skip``/``warning`` để tránh fail sai.
    """
    iv = parse_version(installed)
    if not iv:
        return None
    c = constraint.strip()
    if not c or c.lower() in ("*", "latest", "x", "X"):
        return None  # không ràng buộc khả thi để so sánh -> chưa xác định
    if "lts" in c.lower() or "/" in c:
        return None  # dạng alias (lts/*, node/*...) -> chưa xác định
    # OR
    if "||" in c:
        results = [satisfies(installed, part.strip()) for part in c.split("||")]
        # nếu có vế None (unsupported) -> không thể kết luận chắc chắn -> None
        if any(r is None for r in results):
            return None
        return any(results)
    # khoảng cách (nhiều ràng buộc, cách nhau khoảng trắng)
    parts = c.split()
    if len(parts) > 1:
        results = [satisfies(installed, p) for p in parts]
        if any(r is None for r in results):
            return None
        return all(results)
    single = parts[0]
    # khử dấu v ở đầu
    single = single.lstrip("vV")
    if single.startswith(">="):
        return iv >= parse_version(single[2:])
    if single.startswith(">"):
        return iv > parse_version(single[1:])
    if single.startswith("<="):
        return iv <= parse_version(single[1:])
    if single.startswith("<"):
        return iv < parse_version(single[1:])
    if single.startswith("^"):
        cv = parse_version(single[1:])
        if not cv:
            return None
        return iv[0] == cv[0] and iv >= cv
    if single.startswith("~"):
        cv = parse_version(single[1:])
        if not cv:
            return None
        # ~X.Y.Z -> >= X.Y.Z, < X.(Y+1).0
        if len(cv) >= 2:
            return iv >= cv and iv < (cv[0], cv[1] + 1, 0)
        return iv >= cv
    cv = parse_version(single)
    if not cv:
        return None  # không parse được constraint (vd "~dev") -> chưa xác định
    return iv >= cv  # plain major = minimum major
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
    cfg_file.write_text('[mode]\ndefault = "flat"\n[ai]\nenabled = true\n', encoding="utf-8")
    monkeypatch.delenv("SETUP_DOCTOR_MODE", raising=False)
    cfg = load_config(str(cfg_file), overrides={"mode": "dep"})
    assert cfg.default_mode == "dep"       # CLI wins
    assert cfg.ai.enabled is True          # không bị CLI ghi đè vì overrides không có "ai"


def test_ai_flag_tristate(monkeypatch):
    monkeypatch.delenv("SETUP_DOCTOR_AI", raising=False)
    cfg = load_config(overrides={"ai": True})
    assert cfg.ai.enabled is True
    cfg2 = load_config(overrides={"ai": None})
    assert cfg2.ai.enabled is False        # None = không truyền -> không ghi đè


def test_auto_discover_config_in_repo(tmp_path, monkeypatch):
    (tmp_path / "setup-doctor.toml").write_text('[mode]\ndefault = "flat"\n', encoding="utf-8")
    cfg = load_config(search_from=tmp_path)
    assert cfg.default_mode == "flat"
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


def load_config(
    path: str | None = None,
    overrides: dict | None = None,
    search_from: str | os.PathLike | None = None,
) -> ToolConfig:
    cfg = ToolConfig()
    # Tự tìm config: path truyền rõ -> cwd/repo root -> home
    resolved_path = _resolve_config_path(path, search_from)
    if resolved_path and os.path.isfile(resolved_path):
        with open(resolved_path, "rb") as f:
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
    env_ai = os.environ.get("SETUP_DOCTOR_AI")
    if env_ai is not None:
        cfg.ai.enabled = env_ai.lower() in ("1", "true", "yes")
    ai_model = os.environ.get("SETUP_DOCTOR_AI_MODEL")
    if ai_model:
        cfg.ai.model = ai_model
    # CLI overrides win (chỉ ghi đè khi giá trị được cung cấp thật sự)
    if overrides:
        if overrides.get("mode"):
            cfg.default_mode = overrides["mode"]
        if overrides.get("format"):
            cfg.output_format = overrides["format"]
        if overrides.get("ai") is not None:   # None nghĩa là không truyền cờ
            cfg.ai.enabled = overrides["ai"]
    return cfg


def _resolve_config_path(path, search_from) -> str | None:
    """Tìm config theo thứ tự: path truyền rõ -> search_from/setup-doctor.toml -> home."""
    if path:
        return path
    candidates = []
    if search_from is not None:
        candidates.append(os.path.join(os.fspath(search_from), "setup-doctor.toml"))
    candidates.append(os.path.join(os.getcwd(), "setup-doctor.toml"))
    candidates.append(os.path.join(os.path.expanduser("~"), ".setup-doctor", "setup-doctor.toml"))
    for cand in candidates:
        if os.path.isfile(cand):
            return cand
    return None
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
from importlib import metadata

_CHECK_MARKERS = {
    "node": ("package.json",),
    "python": ("pyproject.toml", "requirements.txt", "setup.py", "setup.cfg", "Pipfile"),
    "java": ("pom.xml", "build.gradle", "build.gradle.kts", "settings.gradle"),
    "dotnet": ("*.sln", "*.csproj", "global.json"),
    "services": ("docker-compose.yml", "docker-compose.yaml", "compose.yml", "compose.yaml", ".env.example"),
}

_SKIP_DIRS = {"node_modules", "venv", ".venv", "__pycache__", ".git", ".idea", ".vscode"}

# Plugin-style: checker đăng ký qua entry points group "setup_doctor.checkers".
# Thêm checker mới = thêm 1 module + khai báo entry point trong pyproject.toml,
# không cần sửa registry.py. (NFR-4)
_ENTRY_POINT_GROUP = "setup_doctor.checkers"


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
    return found


def _load_checker_classes() -> list[type]:
    """Nạp tất cả checker class đã đăng ký qua entry points.

    Fallback: nếu entry points rỗng (vd chạy unit test trước khi cài editable,
    hoặc môi trường không có metadata) → import trực tiếp danh sách built-in,
    để test/CLI vẫn chạy được (điểm review "entry point plugin").
    """
    try:
        eps = metadata.entry_points(group=_ENTRY_POINT_GROUP) if hasattr(metadata, "entry_points") else metadata.entry_points().select(group=_ENTRY_POINT_GROUP)
        classes = [ep.load() for ep in eps]
        if classes:
            return classes
    except Exception:
        pass  # fallback bên dưới
    from .checkers.node import NodeChecker
    from .checkers.python_ck import PythonChecker
    from .checkers.java import JavaChecker
    from .checkers.dotnet_ck import DotnetChecker
    from .checkers.services import ServicesChecker
    from .checkers.registry import RegistryChecker
    return [NodeChecker, PythonChecker, JavaChecker, DotnetChecker,
            ServicesChecker, RegistryChecker]


def get_checkers(ecosystems: set[str]) -> list:
    all_checkers = [cls() for cls in _load_checker_classes()]
    return [c for c in all_checkers if c.ecosystem in ecosystems]
```

`pyproject.toml` — đăng ký entry points cho 6 checker (plugin-style):

```toml
[project.entry-points."setup_doctor.checkers"]
node = "setup_doctor.checkers.node:NodeChecker"
python = "setup_doctor.checkers.python_ck:PythonChecker"
java = "setup_doctor.checkers.java:JavaChecker"
dotnet = "setup_doctor.checkers.dotnet_ck:DotnetChecker"
services = "setup_doctor.checkers.services:ServicesChecker"
registry = "setup_doctor.checkers.registry:RegistryChecker"
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
    assert by_id["node.build.ready"].status == CheckStatus.PASS


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
        version = ""
        version_ok = True
        if present:
            res = run_command([node_exe, "--version"], timeout=10)
            version = res.stdout
            version_ok = res.ok and bool(version)  # exe có trong PATH nhưng --version fail -> FAIL (điểm #5)
        results.append(CheckResult(
            check_id="node.runtime.present",
            name="Node.js runtime present",
            ecosystem=self.ecosystem,
            status=CheckStatus.PASS if (present and version_ok) else CheckStatus.FAIL,
            evidence=f"node {version} at {node_exe}" if (present and version_ok)
                     else ("node found but --version failed" if present else "node not found in PATH"),
            remediation=[] if (present and version_ok) else [
                RemediationStep("Install/uninstall Node.js LTS", "winget install OpenJS.NodeJS.LTS",
                                safe_fix=False),
            ],
        ))

        required = self._required_version(ctx.repo_path)
        if not present or not version_ok:
            results.append(CheckResult(
                check_id="node.sdk.version", name="Node.js SDK version",
                ecosystem=self.ecosystem, status=CheckStatus.SKIP,
                evidence="skipped: runtime not working",
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
            if ok is None:
                # Constraint không hỗ trợ/không parse được -> KHÔNG fail sai; báo warning
                results.append(CheckResult(
                    check_id="node.sdk.version", name="Node.js SDK version",
                    ecosystem=self.ecosystem, severity=Severity.WARNING,
                    status=CheckStatus.FAIL,
                    evidence=f"node {version}; cannot evaluate constraint '{required}'",
                    remediation=[RemediationStep("Check the required engine manually",
                                                 "", safe_fix=False)],
                    depends_on=["node.runtime.present"],
                ))
            else:
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
        # npm thiếu trong repo Node -> FAIL (prerequisite thiếu), không phải SKIP (điểm #5)
        results.append(CheckResult(
            check_id="node.pkgmgr.present", name="npm present",
            ecosystem=self.ecosystem,
            status=CheckStatus.PASS if npm_exe else CheckStatus.FAIL,
            evidence=f"npm at {npm_exe}" if npm_exe else "npm not found in PATH",
            remediation=[] if npm_exe else [
                RemediationStep("Enable corepack/npm", "corepack enable",
                                safe_fix=False, operation="enable-corepack",
                                argv=["corepack", "enable"]),
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
                RemediationStep("Generate lockfile", "npm install --package-lock-only",
                                safe_fix=True, operation="restore-lockfile",
                                argv=["npm", "install", "--package-lock-only"]),
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
                RemediationStep("Install dependencies from lockfile", "npm ci",
                                safe_fix=True, operation="install-node-deps",
                                argv=["npm", "ci"]),
            ],
            depends_on=["node.lockfile.exists", "node.sdk.version"],
        ))

        pkg = self._read_json(ctx.repo_path, "package.json") or {}
        scripts = pkg.get("scripts") or {}
        build_script = scripts.get("build")
        if not build_script:
            results.append(CheckResult(
                check_id="node.build.ready", name="Build tool resolvable",
                ecosystem=self.ecosystem, status=CheckStatus.SKIP,
                evidence="no build script declared",
                depends_on=["node.deps.installed"],
            ))
        else:
            tool = build_script.split()[0]
            bin_path = os.path.join(ctx.repo_path, "node_modules", ".bin", tool)
            tool_ok = os.path.isfile(bin_path) or os.path.isfile(bin_path + ".cmd") or which(tool)
            results.append(CheckResult(
                check_id="node.build.ready", name="Build tool resolvable",
                ecosystem=self.ecosystem,
                status=CheckStatus.PASS if tool_ok else CheckStatus.FAIL,
                evidence=f"build tool '{tool}' resolvable" if tool_ok else f"build tool '{tool}' not resolvable",
                remediation=[] if tool_ok else [
                    RemediationStep("Reinstall dependencies", "npm ci",
                                    safe_fix=True, operation="install-node-deps",
                                    argv=["npm", "ci"]),
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
    # .venv phải có pyvenv.cfg mới hợp lệ (điểm #5)
    (repo / ".venv").mkdir()
    (repo / ".venv" / "pyvenv.cfg").write_text("home = C:\\Python\\3.12\n", encoding="utf-8")
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


def test_python_runtime_version_fails_is_error(fake_runner, monkeypatch, tmp_path):
    repo = _node_context(tmp_path, {"pyproject.toml": '[project]\nrequires-python = ">=3.11"\n'})
    fake_runner.set(["py", "--version"], CommandResult(1, "", "python: error"))
    monkeypatch.setattr("setup_doctor.checkers.python_ck.which",
                        lambda name: "C:\\Python\\py.exe" if name == "py" else None)
    monkeypatch.setattr("setup_doctor.checkers.python_ck.run_command", fake_runner)
    results = PythonChecker().run(CheckContext(repo_path=str(repo), os="windows"))
    by_id = {r.check_id: r for r in results}
    assert by_id["python.runtime.present"].status == CheckStatus.FAIL


def test_python_deps_fail_when_venv_missing(fake_runner, monkeypatch, tmp_path):
    # Có requirements.txt nhưng không có .venv -> deps phải FAIL (không PASS vì không kiểm tra được)
    repo = _node_context(tmp_path, {
        "pyproject.toml": '[project]\nrequires-python = ">=3.11"\n',
        "requirements.txt": "requests==2.31.0\n",
    })
    fake_runner.set(["py", "--version"], CommandResult(0, "Python 3.12.1", ""))
    monkeypatch.setattr("setup_doctor.checkers.python_ck.which",
                        lambda name: "C:\\Python\\py.exe" if name == "py" else None)
    monkeypatch.setattr("setup_doctor.checkers.python_ck.run_command", fake_runner)
    results = PythonChecker().run(CheckContext(repo_path=str(repo), os="windows"))
    by_id = {r.check_id: r for r in results}
    assert by_id["python.env.present"].status == CheckStatus.FAIL
    assert by_id["python.deps.installed"].status == CheckStatus.FAIL
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
        version = ""
        version_ok = True
        if present:
            res = run_command([py_exe, "--version"], timeout=10)
            version = res.stdout
            version_ok = res.ok and bool(version)  # exe có nhưng --version fail -> FAIL (#5)
        results.append(CheckResult(
            check_id="python.runtime.present", name="Python runtime present",
            ecosystem=self.ecosystem,
            status=CheckStatus.PASS if (present and version_ok) else CheckStatus.FAIL,
            evidence=f"python {version} at {py_exe}" if (present and version_ok)
                     else ("python found but --version failed" if present else "no python/py found in PATH"),
            remediation=[] if (present and version_ok) else [
                RemediationStep("Install Python", "winget install Python.Python.3.12", safe_fix=False),
            ],
        ))

        required = self._required_version(ctx.repo_path)
        if not present or not version_ok:
            results.append(CheckResult(
                check_id="python.version", name="Python version",
                ecosystem=self.ecosystem, status=CheckStatus.SKIP,
                evidence="skipped: runtime not working",
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
            if ok is None:
                # Constraint không hỗ trợ -> warning, KHÔNG fail sai (#1)
                results.append(CheckResult(
                    check_id="python.version", name="Python version",
                    ecosystem=self.ecosystem, severity=Severity.WARNING,
                    status=CheckStatus.FAIL,
                    evidence=f"found {version}; cannot evaluate '{required}'",
                    remediation=[RemediationStep("Check requires-python manually", "", safe_fix=False)],
                    depends_on=["python.runtime.present"],
                ))
            else:
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
            evidence=".venv with pyvenv.cfg present" if venv_ok else ".venv missing or invalid (no pyvenv.cfg)",
            remediation=[] if venv_ok else [
                RemediationStep("Create a virtual environment", "py -m venv .venv",
                                safe_fix=True, operation="create-venv",
                                argv=["py", "-m", "venv", ".venv"], files=[".venv"]),
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
        elif not venv_ok:
            # Có requirements nhưng thiếu venv -> không kiểm tra được -> FAIL (không báo pass giả)
            results.append(CheckResult(
                check_id="python.deps.installed", name="Dependencies installed",
                ecosystem=self.ecosystem, status=CheckStatus.FAIL,
                evidence="cannot check deps: venv missing (fix python.env.present first)",
                remediation=[RemediationStep("Create venv then install deps", "py -m venv .venv && pip install -r requirements.txt",
                                             safe_fix=False)],
                depends_on=["python.env.present"],
            ))
        else:
            reqs = [ln.strip() for ln in open(req_path, encoding="utf-8")
                    if ln.strip() and not ln.startswith("#")]
            pip = os.path.join(venv_dir, "Scripts", "pip.exe") if os.name == "nt" else os.path.join(venv_dir, "bin", "pip")
            missing: list[str] = []
            if pip and os.path.isfile(pip):
                res = run_command([pip, "list"], timeout=30)
                installed = res.stdout.lower()
                for r in reqs:
                    pkg = re.split(r"[<>=!~\[;]", r)[0].strip()
                    if pkg and pkg.lower() not in installed:
                        missing.append(pkg)
            else:
                missing = ["<venv missing pip>"]
            results.append(CheckResult(
                check_id="python.deps.installed", name="Dependencies installed",
                ecosystem=self.ecosystem,
                status=CheckStatus.PASS if not missing else CheckStatus.FAIL,
                evidence=f"missing: {', '.join(missing)}" if missing else "requirements satisfied",
                remediation=[] if not missing else [
                    RemediationStep("Install dependencies", "pip install -r requirements.txt",
                                    safe_fix=True, operation="install-python-deps",
                                    argv=["pip", "install", "-r", "requirements.txt"]),
                ],
                depends_on=["python.env.present"],
            ))

        # Read-only: kiểm tra entry point build/test được khai báo (không chạy build).
        has_build_like = False
        pyproject = os.path.join(ctx.repo_path, "pyproject.toml")
        if os.path.isfile(pyproject):
            text = open(pyproject, encoding="utf-8").read()
            has_build_like = ("[project.scripts]" in text or "pytest" in text
                              or "[tool.poetry.scripts]" in text)
        results.append(CheckResult(
            check_id="python.build.ready", name="Build/test entry point declared",
            ecosystem=self.ecosystem,
            status=CheckStatus.PASS if has_build_like else CheckStatus.SKIP,
            evidence="entry point/pytest declared" if has_build_like else "no explicit build entry point",
            depends_on=["python.deps.installed"],
        ))
        return results
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/unit/test_checkers.py -k python -v`
Expected: 4 PASSED  # pass, fail_version, runtime_version_fails, deps_fail_when_venv_missing

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
    monkeypatch.setattr("setup_doctor.checkers.java.which", lambda name: "C:\\java\\java.exe" if name == "java" else ("C:\\maven\\mvn.cmd" if name == "mvn" else None))
    monkeypatch.setattr("setup_doctor.checkers.java.run_command", fake_runner)
    monkeypatch.setattr("setup_doctor.checkers.java._m2_cache_exists", lambda home: True)
    results = JavaChecker().run(CheckContext(repo_path=str(repo), os="windows"))
    # cache có -> java.deps.cached là WARNING (pass nhưng severity warning)
    assert {r.check_id for r in results if r.status == CheckStatus.FAIL} == set()
    cached = next(r for r in results if r.check_id == "java.deps.cached")
    assert cached.severity == Severity.WARNING
    assert cached.status == CheckStatus.PASS


def test_java_fail_version(fake_runner, monkeypatch, tmp_path):
    repo = _node_context(tmp_path, {"pom.xml": "<project><properties><maven.compiler.release>21</maven.compiler.release></properties></project>"})
    fake_runner.set(["java", "-version"], CommandResult(0, 'openjdk version "11.0.20" 2023-07-18', ""))
    monkeypatch.setattr("setup_doctor.checkers.java.which", lambda name: "C:\\java\\java.exe" if name == "java" else ("C:\\maven\\mvn.cmd" if name == "mvn" else None))
    monkeypatch.setattr("setup_doctor.checkers.java.run_command", fake_runner)
    monkeypatch.setattr("setup_doctor.checkers.java._m2_cache_exists", lambda home: True)
    results = JavaChecker().run(CheckContext(repo_path=str(repo), os="windows"))
    assert {r.check_id for r in results if r.status == CheckStatus.FAIL} == {"java.version"}


def test_java_runtime_version_fails_is_error(fake_runner, monkeypatch, tmp_path):
    repo = _node_context(tmp_path, {"pom.xml": "<project/>"})
    fake_runner.set(["java", "-version"], CommandResult(1, "", "error: invalid flag"))
    monkeypatch.setattr("setup_doctor.checkers.java.which", lambda name: "C:\\java\\java.exe" if name == "java" else None)
    monkeypatch.setattr("setup_doctor.checkers.java.run_command", fake_runner)
    results = JavaChecker().run(CheckContext(repo_path=str(repo), os="windows"))
    assert {r.check_id for r in results if r.status == CheckStatus.FAIL} == {"java.runtime.present"}
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
from ..models import CheckResult, RemediationStep, CheckStatus, Severity
from ..utils.commands import run_command, which


def _m2_cache_exists(home: str) -> bool:
    m2 = os.path.join(home, ".m2", "repository")
    return os.path.isdir(m2) and any(os.scandir(m2) for _ in range(1))


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
        version = ""
        version_ok = True
        if present:
            res = run_command([java_exe, "-version"], timeout=10)
            version = res.stderr or res.stdout
            version_ok = res.ok and bool(version)  # exe có nhưng -version fail -> FAIL (#5)
        results.append(CheckResult(
            check_id="java.runtime.present", name="JDK present",
            ecosystem=self.ecosystem,
            status=CheckStatus.PASS if (present and version_ok) else CheckStatus.FAIL,
            evidence=f"java {version} at {java_exe}" if (present and version_ok)
                     else ("java found but -version failed" if present else "java not found in PATH"),
            remediation=[] if (present and version_ok) else [
                RemediationStep("Install a JDK", "winget install EclipseAdoptium.Temurin.21.JDK", safe_fix=False),
            ],
        ))

        required = self._required_major(ctx.repo_path)
        if not present or not version_ok:
            results.append(CheckResult(
                check_id="java.version", name="JDK version",
                ecosystem=self.ecosystem, status=CheckStatus.SKIP,
                evidence="skipped: runtime not working",
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

        # Read-only: chỉ stat cache .m2. Cache tồn tại KHÔNG chứng minh deps repo đã sẵn sàng
        # (điểm #6): chỉ báo warning, không PASS; thiếu cache -> FAIL (gợi ý --fix resolve).
        m2_ok = _m2_cache_exists(os.path.expanduser("~"))
        results.append(CheckResult(
            check_id="java.deps.cached", name="Maven cache populated",
            ecosystem=self.ecosystem,
            severity=Severity.WARNING,
            status=CheckStatus.PASS if m2_ok else CheckStatus.FAIL,
            evidence=("~/.m2/repository populated (không đảm bảo đủ deps cho repo này)" if m2_ok
                     else "~/.m2/repository empty/missing (run --fix to resolve)"),
            remediation=[] if m2_ok else [
                RemediationStep("Resolve dependencies (populates cache)", "mvn dependency:resolve",
                                safe_fix=True, operation="resolve-java-deps",
                                argv=["mvn", "dependency:resolve"]),
            ],
            depends_on=["java.maven.gradle.present"],
        ))

        # Read-only: build file (pom.xml/build.gradle) phải tồn tại + parse được (không chạy build).
        build_file = next((f for f in ("pom.xml", "build.gradle", "build.gradle.kts")
                           if os.path.isfile(os.path.join(ctx.repo_path, f))), None)
        if build_file is None:
            results.append(CheckResult(
                check_id="java.build.ready", name="Build file present",
                ecosystem=self.ecosystem, status=CheckStatus.FAIL,
                evidence="no pom.xml/build.gradle found",
                remediation=[RemediationStep("Project missing build file — check repo contents",
                                             "", safe_fix=False)],
                depends_on=["java.deps.cached"],
            ))
        else:
            results.append(CheckResult(
                check_id="java.build.ready", name="Build file present",
                ecosystem=self.ecosystem, status=CheckStatus.PASS,
                evidence=f"found {build_file}",
                depends_on=["java.deps.cached"],
            ))
        return results
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/unit/test_checkers.py -k java -v`
Expected: 3 PASSED  # pass, fail_version, runtime_version_fails

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
    repo = _node_context(tmp_path, {"global.json": '{"sdk": {"version": "8.0.100"}}', "App.csproj": "<Project Sdk=\"Microsoft.NET.Sdk\" />"})
    fake_runner.set(["dotnet", "--list-sdks"], CommandResult(0, "8.0.100 [C:\\dotnet\\sdk]", ""))
    monkeypatch.setattr("setup_doctor.checkers.dotnet_ck.which", lambda name: "C:\\dotnet\\dotnet.exe" if name == "dotnet" else None)
    monkeypatch.setattr("setup_doctor.checkers.dotnet_ck.run_command", fake_runner)
    monkeypatch.setattr("setup_doctor.checkers.dotnet_ck._nuget_cache_ok", lambda: True)
    results = DotnetChecker().run(CheckContext(repo_path=str(repo), os="windows"))
    assert {r.check_id for r in results if r.status == CheckStatus.FAIL} == set()
    # cache có -> restore.ready là warning (pass nhưng severity warning)
    ready = next(r for r in results if r.check_id == "dotnet.restore.ready")
    assert ready.severity == Severity.WARNING


def test_dotnet_fail_missing_sdk(fake_runner, monkeypatch, tmp_path):
    repo = _node_context(tmp_path, {"global.json": '{"sdk": {"version": "9.0.100"}}', "App.csproj": "<Project Sdk=\"Microsoft.NET.Sdk\" />"})
    fake_runner.set(["dotnet", "--list-sdks"], CommandResult(0, "8.0.100 [C:\\dotnet\\sdk]", ""))
    monkeypatch.setattr("setup_doctor.checkers.dotnet_ck.which", lambda name: "C:\\dotnet\\dotnet.exe" if name == "dotnet" else None)
    monkeypatch.setattr("setup_doctor.checkers.dotnet_ck.run_command", fake_runner)
    monkeypatch.setattr("setup_doctor.checkers.dotnet_ck._nuget_cache_ok", lambda: True)
    results = DotnetChecker().run(CheckContext(repo_path=str(repo), os="windows"))
    assert {r.check_id for r in results if r.status == CheckStatus.FAIL} == {"dotnet.sdk.version"}


def test_dotnet_cli_list_fails_is_error(fake_runner, monkeypatch, tmp_path):
    repo = _node_context(tmp_path, {"App.csproj": "<Project Sdk=\"Microsoft.NET.Sdk\" />"})
    fake_runner.set(["dotnet", "--list-sdks"], CommandResult(1, "", "error"))
    monkeypatch.setattr("setup_doctor.checkers.dotnet_ck.which", lambda name: "C:\\dotnet\\dotnet.exe" if name == "dotnet" else None)
    monkeypatch.setattr("setup_doctor.checkers.dotnet_ck.run_command", fake_runner)
    results = DotnetChecker().run(CheckContext(repo_path=str(repo), os="windows"))
    assert {r.check_id for r in results if r.status == CheckStatus.FAIL} == {"dotnet.runtime.present"}
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
from .base import Checker
from ..models import CheckResult, RemediationStep, CheckStatus, Severity
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

    def _nuget_cache_ok(self) -> bool:
        return os.path.isdir(os.path.join(os.path.expanduser("~"), ".nuget", "packages"))

    def run(self, ctx):
        results = []
        dt = which("dotnet")
        present = dt is not None
        installed = ""
        list_ok = True
        if present:
            res = run_command([dt, "--list-sdks"], timeout=10)
            installed = res.stdout
            list_ok = res.ok  # exe có nhưng lệnh fail -> FAIL (#5)
        results.append(CheckResult(
            check_id="dotnet.runtime.present", name="dotnet CLI present",
            ecosystem=self.ecosystem,
            status=CheckStatus.PASS if (present and list_ok) else CheckStatus.FAIL,
            evidence=f"dotnet at {dt}" if (present and list_ok)
                     else ("dotnet found but --list-sdks failed" if present else "dotnet not found in PATH"),
            remediation=[] if (present and list_ok) else [
                RemediationStep("Install the .NET SDK", "winget install Microsoft.DotNet.SDK.8", safe_fix=False),
            ],
        ))

        required = self._required_version(ctx.repo_path)
        if not present or not list_ok:
            results.append(CheckResult(
                check_id="dotnet.sdk.version", name=".NET SDK version",
                ecosystem=self.ecosystem, status=CheckStatus.SKIP,
                evidence="skipped: cli not working",
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

        # Read-only: chỉ stat NuGet cache. Cache tồn tại KHÔNG chứng minh deps repo sẵn sàng (điểm #6)
        # -> warning khi có cache (pass với severity warning), FAIL khi thiếu.
        cache_ok = self._nuget_cache_ok()
        results.append(CheckResult(
            check_id="dotnet.restore.ready", name="NuGet packages cached",
            ecosystem=self.ecosystem,
            severity=Severity.WARNING,
            status=CheckStatus.PASS if cache_ok else CheckStatus.FAIL,
            evidence=("~/.nuget/packages exists (không đảm bảo đủ deps cho repo này)" if cache_ok
                     else "~/.nuget/packages missing (run --fix to restore)"),
            remediation=[] if cache_ok else [
                RemediationStep("Restore packages (populates cache)", "dotnet restore",
                                safe_fix=True, operation="restore-dotnet",
                                argv=["dotnet", "restore"]),
            ],
            depends_on=["dotnet.sdk.version"],
        ))

        # Read-only: kiểm tra build file tồn tại + parse được
        proj_files = [f for f in os.listdir(ctx.repo_path)
                      if f.endswith((".sln", ".csproj", ".fsproj", ".vbproj")) and os.path.isfile(os.path.join(ctx.repo_path, f))]
        if not proj_files:
            results.append(CheckResult(
                check_id="dotnet.build.ready", name="Build files present",
                ecosystem=self.ecosystem, status=CheckStatus.SKIP,
                evidence="no .sln/.csproj found",
                depends_on=["dotnet.restore.ready"],
            ))
        else:
            results.append(CheckResult(
                check_id="dotnet.build.ready", name="Build files present",
                ecosystem=self.ecosystem, status=CheckStatus.PASS,
                evidence=f"found: {', '.join(proj_files)}",
                depends_on=["dotnet.restore.ready"],
            ))
        return results
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/unit/test_checkers.py -k dotnet -v`
Expected: 3 PASSED  # pass, fail_missing_sdk, cli_list_fails

- [ ] **Step 5: Commit**

```bash
git add src/setup_doctor/checkers/dotnet_ck.py tests/unit/test_checkers.py
git commit -m "feat: dotnet checker (cli, pinned sdk version, cache readiness)"
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


def test_services_missing_docker_is_fail(fake_runner, monkeypatch, tmp_path):
    # Repo có docker-compose nhưng docker không cài -> container.present phải FAIL (không SKIP)
    repo = _node_context(tmp_path, {"docker-compose.yml": "services:\n  db:\n    image: postgres:16\n"})
    monkeypatch.setattr("setup_doctor.checkers.services.which", lambda name: None)
    results = ServicesChecker().run(CheckContext(repo_path=str(repo), os="windows"))
    by_id = {r.check_id: r for r in results}
    assert by_id["services.container.present"].status == CheckStatus.FAIL
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
from ..models import CheckResult, RemediationStep, CheckStatus, Severity
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
        if docker is not None:
            docker_ok = run_command([docker, "info"], timeout=10).ok
        else:
            docker_ok = False
        # Docker thiếu khi repo yêu cầu compose -> FAIL (prerequisite thiếu), không SKIP (#5)
        results.append(CheckResult(
            check_id="services.container.present", name="Docker daemon reachable",
            ecosystem=self.ecosystem,
            status=CheckStatus.PASS if docker_ok
                   else (CheckStatus.FAIL if has_compose else CheckStatus.SKIP),
            evidence="docker daemon reachable" if docker_ok
                     else ("docker missing/unavailable (required by compose)" if has_compose else "no compose; docker not needed"),
            remediation=[] if docker_ok else [
                RemediationStep("Start Docker Desktop", "start \"\" \"C:\\Program Files\\Docker\\Docker\\Docker Desktop.exe\"",
                                safe_fix=False, operation="start-docker",
                                argv=["start", "", "C:\\Program Files\\Docker\\Docker\\Docker Desktop.exe"]),
            ],
        ))

        expected = set(self._compose_services(ctx.repo_path))
        if docker_ok and expected:
            res = run_command([docker, "compose", "ps", "--format", "{{.Name}}"], cwd=ctx.repo_path, timeout=30)
            running = set(res.stdout.splitlines())
            # Container name = <project>-<service>-1; so theo PREFIX (không đòi khớp chính xác) (#5)
            def _running(key):
                return any(rn == key or rn.startswith(key + "-") or rn.endswith("-" + key + "-1")
                           for rn in running)
            missing = {k for k in expected if not _running(k)} if res.ok else set(expected)
            results.append(CheckResult(
                check_id="services.compose.up", name="Compose services running",
                ecosystem=self.ecosystem,
                status=CheckStatus.PASS if not missing else CheckStatus.FAIL,
                evidence=f"not running: {', '.join(sorted(missing))}" if missing else "all compose services running",
                remediation=[] if not missing else [
                    RemediationStep("Start compose services", "docker compose up -d",
                                    safe_fix=True, operation="start-service",
                                    argv=["docker", "compose", "up", "-d"]),
                ],
                depends_on=["services.container.present"],
            ))
        elif has_compose and not docker_ok:
            results.append(CheckResult(
                check_id="services.compose.up", name="Compose services running",
                ecosystem=self.ecosystem, status=CheckStatus.FAIL,
                evidence="cannot check: docker unavailable",
                remediation=[RemediationStep("Start Docker first", "", safe_fix=False)],
                depends_on=["services.container.present"],
            ))
        else:
            results.append(CheckResult(
                check_id="services.compose.up", name="Compose services running",
                ecosystem=self.ecosystem, status=CheckStatus.SKIP,
                evidence="no compose file",
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
                        RemediationStep(f"Start {label}", f"docker compose up -d {key}",
                                        safe_fix=True, operation="start-service",
                                        argv=["docker", "compose", "up", "-d", key]),
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
                remediation=[RemediationStep("Create .env from template", "create-env",
                                             safe_fix=True, operation="create-env",
                                             argv=None, files=[".env.example", ".env"])],
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
Expected: 3 PASSED  # fail_no_env, db_port_closed, missing_docker_is_fail

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


def test_registry_git_user_warning_ssh_skip_https(fake_runner, monkeypatch, tmp_path):
    repo = _node_context(tmp_path, {})
    # remote là HTTPS -> SSH check skip
    (repo / ".git").mkdir()
    (repo / ".git" / "config").write_text("[remote \"origin\"]\n\turl = https://github.com/example/repo.git\n", encoding="utf-8")
    fake_runner.set(["git", "config", "--get", "user.name"], CommandResult(0, "Alice", ""))
    fake_runner.set(["git", "config", "--get", "user.email"], CommandResult(0, "alice@example.com", ""))
    monkeypatch.setattr("setup_doctor.checkers.registry.which", lambda name: "C:\\git\\git.exe" if name == "git" else None)
    monkeypatch.setattr("setup_doctor.checkers.registry.run_command", fake_runner)
    monkeypatch.setattr("setup_doctor.checkers.registry._ssh_key_exists", lambda: False)
    results = RegistryChecker().run(CheckContext(repo_path=str(repo), os="windows", config=object()))
    by_id = {r.check_id: r for r in results}
    assert by_id["registry.git.user"].status == CheckStatus.PASS
    assert by_id["registry.git.ssh"].status == CheckStatus.SKIP  # remote HTTPS -> không cần SSH


def test_registry_git_user_missing_is_warning_not_error(fake_runner, monkeypatch, tmp_path):
    repo = _node_context(tmp_path, {})
    (repo / ".git").mkdir()
    (repo / ".git" / "config").write_text("[remote \"origin\"]\n\turl = git@github.com:example/repo.git\n", encoding="utf-8")
    fake_runner.set(["git", "config", "--get", "user.name"], CommandResult(1, "", ""))
    fake_runner.set(["git", "config", "--get", "user.email"], CommandResult(1, "", ""))
    monkeypatch.setattr("setup_doctor.checkers.registry.which", lambda name: "C:\\git\\git.exe" if name == "git" else None)
    monkeypatch.setattr("setup_doctor.checkers.registry.run_command", fake_runner)
    monkeypatch.setattr("setup_doctor.checkers.registry._ssh_key_exists", lambda: True)
    results = RegistryChecker().run(CheckContext(repo_path=str(repo), os="windows", config=object()))
    by_id = {r.check_id: r for r in results}
    assert by_id["registry.git.user"].status == CheckStatus.FAIL
    assert by_id["registry.git.user"].severity == Severity.WARNING
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
from ..models import CheckResult, RemediationStep, CheckStatus, Severity
from ..utils.commands import run_command, which

_SSH_KEYS = ("id_ed25519", "id_rsa", "id_ecdsa")


def _ssh_key_exists() -> bool:
    home = os.path.expanduser("~")
    return any(os.path.isfile(os.path.join(home, ".ssh", k)) for k in _SSH_KEYS)


def _git_remote_uses_ssh(repo_path: str) -> bool:
    """Đọc .git/config (không chạy lệnh) để xác định remote có dùng SSH hay không."""
    cfg_path = os.path.join(repo_path, ".git", "config")
    if not os.path.isfile(cfg_path):
        return False
    with open(cfg_path, encoding="utf-8", errors="replace") as f:
        text = f.read()
    return "git@" in text or "ssh://" in text


class RegistryChecker(Checker):
    id, label, ecosystem = "registry", "Registry/credentials", "registry"

    def run(self, ctx):
        results = []
        git = which("git")
        if git:
            name = run_command([git, "config", "--get", "user.name"], timeout=10)
            email = run_command([git, "config", "--get", "user.email"], timeout=10)
            ok = name.ok and email.ok
            # Git user chỉ là warning (không chặn build dự án)
            results.append(CheckResult(
                check_id="registry.git.user", name="git user configured",
                ecosystem=self.ecosystem,
                severity=Severity.WARNING,
                status=CheckStatus.PASS if ok else CheckStatus.FAIL,
                evidence="user.name/email set" if ok else "git user.name/email not set",
                remediation=[] if ok else [
                    RemediationStep("Set git identity",
                                    'git config --global user.name "Your Name"',
                                    safe_fix=False),
                    RemediationStep("Set git email",
                                    'git config --global user.email "you@example.com"',
                                    safe_fix=False),
                ],
            ))
        else:
            results.append(CheckResult(
                check_id="registry.git.user", name="git user configured",
                ecosystem=self.ecosystem, status=CheckStatus.SKIP,
                evidence="git not found",
            ))

        # SSH chỉ cần khi remote dùng SSH; HTTPS thì skip để tránh fail giả
        if _git_remote_uses_ssh(ctx.repo_path):
            ssh_ok = _ssh_key_exists()
            results.append(CheckResult(
                check_id="registry.git.ssh", name="SSH key present",
                ecosystem=self.ecosystem,
                severity=Severity.WARNING,
                status=CheckStatus.PASS if ssh_ok else CheckStatus.FAIL,
                evidence="ssh key found" if ssh_ok else "no ssh key in ~/.ssh",
                remediation=[] if ssh_ok else [
                    RemediationStep("Generate an SSH key", "ssh-keygen -t ed25519 -C \"you@example.com\"", safe_fix=False),
                ],
            ))
        else:
            results.append(CheckResult(
                check_id="registry.git.ssh", name="SSH key present",
                ecosystem=self.ecosystem, status=CheckStatus.SKIP,
                evidence="remote uses HTTPS; no SSH key needed",
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
Expected: 2 PASSED  # git_user_warning_ssh_skip_https, git_user_missing_is_warning

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
    assert checks[1].causes == ["sdk"]
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


def test_dep_multiple_dependencies_fail_lists_all_roots():
    # node.deps.installed phụ thuộc cả lockfile + SDK; cả hai fail -> 2 root causes
    checks = [
        CheckResult("sdk", "SDK", "node", status=CheckStatus.FAIL, depends_on=[]),
        CheckResult("lock", "Lock", "node", status=CheckStatus.FAIL, depends_on=[]),
        CheckResult("deps", "Deps", "node", status=CheckStatus.FAIL,
                    depends_on=["lock", "sdk"]),
    ]
    report = diagnose(checks, "dep", "/repo", "windows")
    rc_ids = {rc.cause_check_id for rc in report.diagnosis.root_causes}
    assert rc_ids == {"sdk", "lock"}
    assert checks[2].caused_by == "lock"  # primary = root đầu tiên theo thứ tự ổn định
    assert set(checks[2].causes) == {"lock", "sdk"}
    # deps có mặt trong affected của CẢ HAI root causes
    for rc in report.diagnosis.root_causes:
        assert "deps" in rc.affected_checks


def test_dep_skip_dependency_bridges_to_root():
    # runtime SKIP vì... thực tế: nếu runtime SKIP vì tool thiếu, và child phụ thuộc runtime FAIL
    # thì engine phải nối child về root cause của runtime nếu có; nếu runtime là SKIP (không fail)
    # và con phụ thuộc nó -> chain phải thể hiện "blocked by skip".
    checks = [
        CheckResult("runtime", "Runtime", "node", status=CheckStatus.SKIP),
        CheckResult("sdk", "SDK", "node", status=CheckStatus.FAIL, depends_on=["runtime"]),
    ]
    report = diagnose(checks, "dep", "/repo", "windows")
    assert len(report.diagnosis.root_causes) == 1
    assert report.diagnosis.root_causes[0].cause_check_id == "sdk"
    # sdk phụ thuộc skip nhưng bản thân fail -> vẫn là root cause (không có failed dep)


def test_dep_cycle_does_not_loop():
    checks = [
        CheckResult("a", "A", "node", status=CheckStatus.FAIL, depends_on=["b"]),
        CheckResult("b", "B", "node", status=CheckStatus.FAIL, depends_on=["a"]),
    ]
    report = diagnose(checks, "dep", "/repo", "windows")
    # chu trình a<->b: xử lý an toàn, không treo; ít nhất 1 root cause xác định được
    ids = {rc.cause_check_id for rc in report.diagnosis.root_causes}
    assert ids  # non-empty
    assert len(report.diagnosis.root_causes) >= 1


def test_dep_depends_on_missing_id_is_ignored_safely():
    checks = [CheckResult("a", "A", "node", status=CheckStatus.FAIL,
                          depends_on=["does-not-exist"])]
    report = diagnose(checks, "dep", "/repo", "windows")
    assert len(report.diagnosis.root_causes) == 1
    assert report.diagnosis.root_causes[0].cause_check_id == "a"
    assert checks[0].caused_by is None
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/unit/test_engine.py -k dep -v`
Expected: FAIL (`diagnosis` is `None` in dep mode yet, or wrong grouping)

- [ ] **Step 3: Implement the DAG logic**

Append to `src/setup_doctor/engine.py`:

```python
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
        c.caused_by = None if c.check_id in roots else (c.causes[0] if c.causes else None)
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
```

> **Ghi chú (điểm #2 review):** `caused_by` giữ **primary root cause** (root đầu tiên theo thứ tự ổn định) để giữ API quen thuộc; **`causes`** chứa **toàn bộ** root causes — đáp ứng trường hợp multi-dependency fail. Nếu check phụ thuộc nhiều root, check đó xuất hiện trong `affected_checks` của cả các root đó.

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/unit/test_engine.py -v`
Expected: 11 PASSED  # 4 flat + 7 dep (multi-root, skip-bridge, cycle, missing-id...)

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
      "remediation": [{"step": "Install node 22", "command": "nvm install 22", "safe_fix": false, "source": "manual", "files": [], "operation": null, "argv": null}],
      "depends_on": ["runtime"],
      "caused_by": null,
      "causes": ["sdk"]
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
      "caused_by": "sdk",
      "causes": ["sdk"]
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
from setup_doctor.fixer import Fixer, OperationNotAllowedError
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
    # create-env (reversible, đã backup .env) thành công; npm ci (non-reversible) fail
    # -> chỉ bước reversible được rollback; npm ci ghi rõ "failed / non-reversible".
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
    # .env không tồn tại trước; create-env tạo nó; npm ci fail -> .env bị xóa
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


def test_fixer_rejects_path_outside_repo(fake_runner, monkeypatch, tmp_path):
    outside = [CheckResult("x", "x", "services", status=CheckStatus.FAIL,
                           remediation=[_step("create-env", "Create .env", [],
                                              files=["../outside.env", ".env"])])]
    report = Report(repo_path=str(tmp_path), os="windows", summary={}, checks=outside)
    fix = Fixer(str(tmp_path)).apply(report)
    # file ngoài repo bị chặn -> step không chạy
    assert fix.entries[0].status == "skipped"
    assert "outside repo" in fix.entries[0].detail.lower() or "path" in fix.entries[0].detail.lower()
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


class OperationNotAllowedError(Exception):
    """Op không nằm trong whitelist fix (không được tự chạy)."""


# Whitelist op: chỉ những op này mới được tự chạy khi --fix.
# - argv: lệnh thực thi (list, KHÔNG shell operator).
# - reversible: True = có thể rollback bằng backup file (chỉ áp dụng cho file
#   cấu hình nhỏ đã khai báo); False = KHÔNG thể rollback (install/restore/
#   start-service/cache toàn cục) — chỉ log rõ, không hứa khôi phục.
# - timeout: riêng cho op fix (npm ci/mvn resolve/dotnet restore có thể lâu);
#   KHÔNG ràng buộc bởi NFR-3 (30s cho lệnh check).
_WHITELIST_OP: dict[str, dict] = {
    "install-node-deps":  {"argv": ["npm", "ci"], "reversible": False, "timeout": 180},
    "install-yarn-deps":  {"argv": ["yarn", "install", "--frozen-lockfile"], "reversible": False, "timeout": 180},
    "create-venv":        {"argv": ["py", "-m", "venv", ".venv"], "reversible": False, "timeout": 60},
    "install-python-deps":{"argv": ["pip", "install", "-r", "requirements.txt"], "reversible": False, "timeout": 180},
    "resolve-java-deps":  {"argv": ["mvn", "dependency:resolve"], "reversible": False, "timeout": 300},
    "restore-dotnet":     {"argv": ["dotnet", "restore"], "reversible": False, "timeout": 300},
    "start-service":      {"argv": ["docker", "compose", "up", "-d"], "reversible": False, "timeout": 180},
    "create-env":         {"argv": None, "reversible": True, "timeout": 5},  # Python: copy .env.example -> .env
    "restore-lockfile":   {"argv": ["npm", "install", "--package-lock-only"], "reversible": False, "timeout": 120},
    "enable-corepack":    {"argv": ["corepack", "enable"], "reversible": False, "timeout": 60},
    "start-docker":       {"argv": ["start", "", r"C:\Program Files\Docker\Docker\Docker Desktop.exe"],
                           "reversible": False, "timeout": 30,
                           "note": "Windows-only; Linux/macOS roadmap"},
}


@dataclass
class FixLogEntry:
    command: str
    status: str  # applied | skipped | failed | rolled_back
    operation: str = ""
    detail: str = ""
    reversible: bool = False


@dataclass
class FixReport:
    backup_dir: str
    entries: list[FixLogEntry] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "backup_dir": self.backup_dir,
            "entries": [{"command": e.command, "status": e.status,
                         "operation": e.operation, "detail": e.detail,
                         "reversible": e.reversible} for e in self.entries],
        }


class Fixer:
    BACKUP_DIR_NAME = ".setup-doctor-backup"

    def __init__(self, repo_path: str):
        self.repo_path = os.path.abspath(repo_path)
        # Timestamp đủ phân giải (microsecond) để tránh trùng khi chạy 2 lần nhanh.
        stamp = datetime.datetime.now().strftime("%Y%m%d-%H%M%S-%f")
        self.backup_dir = os.path.join(self.repo_path, self.BACKUP_DIR_NAME, stamp)

    def _is_inside_repo(self, rel: str) -> bool:
        """Chặn path traversal: file khai báo phải nằm trong repo."""
        full = os.path.normpath(os.path.join(self.repo_path, rel))
        return os.path.commonpath([self.repo_path, full]) == self.repo_path

    def _backup_file(self, rel: str) -> None:
        src = os.path.join(self.repo_path, rel)
        if not os.path.exists(src):
            return
        dst = os.path.join(self.backup_dir, rel)
        os.makedirs(os.path.dirname(dst), exist_ok=True)
        shutil.copy2(src, dst)

    def _restore_file(self, rel: str) -> None:
        """Khôi phục file từ backup; nếu file do fix tạo mới (không backup) -> xóa đi."""
        dst = os.path.join(self.backup_dir, rel)
        target = os.path.join(self.repo_path, rel)
        if os.path.exists(dst):
            os.makedirs(os.path.dirname(target), exist_ok=True)
            shutil.copy2(dst, target)
        else:
            if os.path.exists(target):
                os.remove(target)

    def _apply_create_env(self, entry: FixLogEntry) -> None:
        """create-env (reversible): copy .env.example -> .env bằng Python."""
        example = os.path.join(self.repo_path, ".env.example")
        target = os.path.join(self.repo_path, ".env")
        if not os.path.isfile(example):
            entry.status = "failed"
            entry.detail = ".env.example missing"
            return
        try:
            with open(example, encoding="utf-8") as f:
                content = f.read()
            with open(target, "w", encoding="utf-8") as f:
                f.write(content)
            entry.status = "applied"
        except OSError as exc:
            entry.status = "failed"
            entry.detail = str(exc)

    def _apply_step(self, step, entry: FixLogEntry) -> None:
        # 1) Kiểm tra toàn bộ file khai báo nằm trong repo (chống path traversal).
        for rel in step.files:
            if not self._is_inside_repo(rel):
                entry.status = "skipped"
                entry.detail = f"path outside repo: {rel}"
                return
        # 2) Backup các file khai báo (chỉ file cấu hình nhỏ, đã kiểm tra trong repo).
        for rel in step.files:
            self._backup_file(rel)
        # 3) Thực thi theo operation whitelist.
        op = _WHITELIST_OP.get(step.operation)
        if op is None:
            entry.status = "skipped"
            entry.detail = f"operation not allowed: {step.operation}"
            return
        if step.operation == "create-env":
            self._apply_create_env(entry)
            return
        res = run_command(op["argv"], cwd=self.repo_path, timeout=op["timeout"])
        if res.ok:
            entry.status = "applied"
        else:
            entry.status = "failed"
            entry.detail = res.stderr

    def apply(self, report: Report) -> FixReport:
        os.makedirs(self.backup_dir, exist_ok=True)
        fix_report = FixReport(backup_dir=self.backup_dir)
        applied_reversible: list[tuple] = []  # các bước reversible đã apply -> có thể rollback
        for c in report.checks:
            if c.status.value != "fail":
                continue
            for step in c.remediation:
                op = _WHITELIST_OP.get(step.operation or "")
                entry = FixLogEntry(
                    command=step.command or (op["argv"][0] if op and op["argv"] else ""),
                    status="skipped",
                    operation=step.operation or "",
                    reversible=bool(op and op["reversible"]),
                )
                if not step.safe_fix or step.source != "manual" or step.operation is None:
                    entry.detail = "not safe_fix / not manual / no operation"
                else:
                    self._apply_step(step, entry)
                    if entry.status == "applied":
                        if entry.reversible:
                            applied_reversible.append((step, entry))
                    elif entry.status == "failed":
                        # Transaction: rollback các bước REVERSIBLE đã apply.
                        # Các op non-reversible (npm ci/mvn/docker) ĐÃ CHẠY THÀNH CÔNG
                        # trước đó không thể khôi phục — chỉ ghi rõ trong log.
                        for prev_step, prev_entry in applied_reversible:
                            for rel in prev_step.files:
                                self._restore_file(rel)
                            prev_entry.status = "rolled_back"
                        applied_reversible.clear()
                fix_report.entries.append(entry)
                if entry.status == "failed":
                    # Dừng toàn bộ nếu có bước fail (tránh chồng thêm lỗi).
                    for e in fix_report.entries:
                        if e.status in ("skipped",) and e.operation in _WHITELIST_OP:
                            pass
                    return fix_report
        return fix_report
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/integration/test_fixer.py -v`
Expected: 5 PASSED  # applies_safe, rolls_back_reversible, removes_new_created, rejects_unknown_op, rejects_path_outside

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


class AICallQuota:
    """Quota chung cho TẤT CẢ AI calls trong một lần chạy (remediation + explainer)."""

    def __init__(self, max_requests: int):
        self._remaining = max_requests

    def take(self) -> bool:
        if self._remaining <= 0:
            return False
        self._remaining -= 1
        return True

    @property
    def remaining(self) -> int:
        return self._remaining
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
from setup_doctor.ai import AICallQuota
from setup_doctor.models import CheckResult, CheckStatus, RemediationStep, Diagnosis, RootCause


def _quota(n=100):
    return AICallQuota(n)


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
    steps = AIRemediation(provider, _quota()).suggest(cr, "windows")
    assert steps[0].command == "nvm install 22"      # manual first
    assert steps[-1].source == "ai"
    assert steps[-1].safe_fix is False


def test_ai_remediation_falls_back_on_error():
    cr = CheckResult("sdk", "SDK", "node", status=CheckStatus.FAIL, evidence="18 < 20",
                     remediation=[RemediationStep("Install Node", "nvm install 22")])
    steps = AIRemediation(FakeProvider(None, error=True), _quota()).suggest(cr, "windows")
    assert len(steps) == 1
    assert steps[0].command == "nvm install 22"


def test_ai_remediation_honors_shared_quota():
    cr = CheckResult("sdk", "SDK", "node", status=CheckStatus.FAIL, evidence="18 < 20",
                     remediation=[RemediationStep("Install Node", "nvm install 22")])
    quota = _quota(1)  # chỉ cho phép 1 AI call
    steps1 = AIRemediation(FakeProvider({"suggestions": []}), quota).suggest(cr, "windows")
    steps2 = AIRemediation(FakeProvider({"suggestions": []}), quota).suggest(cr, "windows")
    assert quota.remaining == 0
    assert len(steps2) == 1  # call thứ 2 bị chặn -> chỉ còn manual


def test_ai_remediation_sanitizes_evidence(monkeypatch):
    manual = [RemediationStep("Install Node", "nvm install 22", safe_fix=False)]
    cr = CheckResult("sdk", "SDK", "node", status=CheckStatus.FAIL,
                     evidence="C:\\Users\\alice\\repo\nhttps://registry.example.com/npm\nsk-abc123secret",
                     remediation=manual)
    captured = {}
    class Recorder(AIProvider):
        def complete(self, system, user, response_schema):
            captured["user"] = user
            return {"suggestions": []}
    AIRemediation(Recorder(), _quota()).suggest(cr, "windows")  # type: ignore[arg-type]
    assert "C:\\Users\\alice" not in captured["user"]
    assert "registry.example.com" not in captured["user"]
    assert "sk-abc123secret" not in captured["user"]


def test_ai_remediation_validates_schema_and_falls_back():
    cr = CheckResult("sdk", "SDK", "node", status=CheckStatus.FAIL, evidence="18 < 20",
                     remediation=[RemediationStep("Install Node", "nvm install 22")])
    class BadProvider(AIProvider):
        def complete(self, system, user, response_schema):
            return {"suggestions": [{"step": "x"}]}  # thiếu command -> invalid
    steps = AIRemediation(BadProvider(), _quota()).suggest(cr, "windows")  # type: ignore[arg-type]
    assert len(steps) == 1
    assert steps[0].command == "nvm install 22"  # fallback manual


def test_ai_explainer_returns_text():
    diag = Diagnosis(root_causes=[RootCause("sdk", "msg", ["a"], "a → b")])
    provider = FakeProvider({"explanation": "Vì SDK thiếu nên deps không cài được."})
    assert AIExplainer(provider, _quota()).explain(diag) == "Vì SDK thiếu nên deps không cài được."


def test_ai_explainer_none_on_error():
    diag = Diagnosis(root_causes=[RootCause("sdk", "msg", ["a"], "a → b")])
    assert AIExplainer(FakeProvider(None, error=True), _quota()).explain(diag) is None
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/unit/test_ai.py -v`
Expected: FAIL (`ModuleNotFoundError: No module named 'setup_doctor.ai.remediation'`)

- [ ] **Step 3: Implement remediation + explainer**

```python
# src/setup_doctor/ai/remediation.py
from __future__ import annotations
import re
from ..models import CheckResult, RemediationStep

_SYSTEM_PROMPT = (
    "You are a developer-environment troubleshooting assistant. "
    "Given a failing setup check, suggest 1-3 concrete fix commands for the given OS. "
    'Reply with JSON only: {"suggestions": [{"step": "...", "command": "..."}]}. '
    "Commands must be copy-pasteable and specific."
)

# Redaction: loại bỏ thông tin nhạy cảm khỏi evidence trước khi gửi lên LLM (NFR-8).
_PATH_RE = re.compile(r"[A-Za-z]:\\[^\s\"']+|/\S+/\S+")
_URL_RE = re.compile(r"https?://\S+")
_SECRET_RE = re.compile(r"(sk-|ghp_|AKIA|-----BEGIN)[A-Za-z0-9_\-]{6,}")


def sanitize(text: str) -> str:
    if not text:
        return text
    text = _URL_RE.sub("<url>", text)
    text = _PATH_RE.sub("<path>", text)
    text = _SECRET_RE.sub("<secret>", text)
    return text


def _is_valid_data(data) -> bool:
    """Validate schema trước khi hiển thị (NFR-8)."""
    if not isinstance(data, dict):
        return False
    suggs = data.get("suggestions")
    if not isinstance(suggs, list):
        return False
    for item in suggs:
        if not isinstance(item, dict):
            return False
        if not item.get("step") or not item.get("command"):  # cả step và command bắt buộc
            return False
    return True


class AIRemediation:
    def __init__(self, provider, quota: "AICallQuota"):
        self._provider = provider
        self._quota = quota

    def suggest(self, check: CheckResult, os_name: str) -> list[RemediationStep]:
        manual = list(check.remediation)
        if not self._quota.take():
            return manual
        user = (f"OS: {os_name}\ncheck_id: {check.check_id}\n"
                f"evidence: {sanitize(check.evidence)}\n")
        try:
            data = self._provider.complete(_SYSTEM_PROMPT, user, dict)
        except Exception:
            return manual
        if not _is_valid_data(data):
            return manual
        for item in data["suggestions"]:
            manual.append(RemediationStep(
                step=str(item["step"]),
                command=str(item["command"]),
                safe_fix=False,
                source="ai",
            ))
        return manual
```

```python
# src/setup_doctor/ai/explainer.py
from __future__ import annotations
from ..models import Diagnosis
from .remediation import sanitize

_SYSTEM_PROMPT = (
    "You explain developer setup failures concisely. "
    'Reply with JSON only: {"explanation": "..."} — max 3 sentences. '
    "Explain the root cause first, then what breaks downstream."
)


def _is_valid_explanation(data) -> bool:
    return isinstance(data, dict) and isinstance(data.get("explanation"), str) and bool(data["explanation"])


class AIExplainer:
    def __init__(self, provider, quota: "AICallQuota"):
        self._provider = provider
        self._quota = quota

    def explain(self, diagnosis: Diagnosis | None) -> str | None:
        if not diagnosis or not diagnosis.root_causes:
            return None
        if not self._quota.take():
            return None
        chains = "; ".join(rc.chain for rc in diagnosis.root_causes)
        messages = "; ".join(sanitize(rc.message) for rc in diagnosis.root_causes)
        user = f"Root cause chains: {chains}\nMessages: {messages}"
        try:
            data = self._provider.complete(_SYSTEM_PROMPT, user, dict)
        except Exception:
            return None
        if not _is_valid_explanation(data):
            return None
        return data["explanation"]
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/unit/test_ai.py -v`
Expected: 10 PASSED  # 3 (provider) + 7 (remediation/explainer/quota/sanitize/schema)

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
    gt = {"expected_failures": ["a", "b"], "expected_passes": ["c"]}
    m = compute_metrics(_report(), gt)
    assert m["tp"] == 2
    assert m["fp"] == 0
    assert m["fn"] == 0
    assert m["tn"] == 1
    assert m["precision"] == 1.0
    assert m["recall"] == 1.0
    assert m["f1"] == 1.0
    assert m["accuracy"] == 1.0  # (2+1)/3 universe


def test_metrics_recall_partial():
    # "zz" nằm trong expected_failures -> THUỘC universe. Tool không emit check "zz"
    # -> FN=1 (theo quy tắc 4.6, ID trong GT luôn thuộc universe; không emit = FN).
    gt = {"expected_failures": ["a", "b", "zz"], "expected_passes": ["c"]}
    m = compute_metrics(_report(), gt)
    assert m["recall"] == 2 / 3
    assert m["fn"] == 1
    assert m["accuracy"] == 3 / 4  # (tp=2 + tn=1) / universe(4: a,b,c,zz)


def test_metrics_missing_emit_is_fn():
    # ground truth gán fail cho check KHÔNG có trong report -> FN (tool không emit)
    gt = {"expected_failures": ["a", "zz"], "expected_passes": []}
    m = compute_metrics(_report(), gt)
    assert m["fn"] == 1  # zz không emit -> FN


def test_metrics_fp_only_when_gt_explicitly_passes():
    # Tool báo fail cho check "d" (KHÔNG có trong ground truth) -> không tính FP
    # (check chưa được gán nhãn, không phạt tool vì phát hiện thêm).
    checks = _report().checks + [CheckResult("d", "D", "node", status=CheckStatus.FAIL)]
    report = Report(repo_path="/r", os="windows", mode="flat", summary={}, checks=checks)
    gt = {"expected_failures": ["a", "b"], "expected_passes": ["c"]}
    m = compute_metrics(report, gt)
    assert m["fp"] == 0
    assert m["precision"] == 1.0


def test_metrics_fp_when_gt_passes_but_tool_fails():
    checks = [CheckResult("a", "A", "node", status=CheckStatus.FAIL)]
    report = Report(repo_path="/r", os="windows", mode="flat", summary={}, checks=checks)
    gt = {"expected_failures": [], "expected_passes": ["a"]}
    m = compute_metrics(report, gt)
    assert m["fp"] == 1
    assert m["precision"] == 0.0


def test_validate_ground_truth_rejects_unknown_ids():
    # ID trong ground truth phải thuộc catalog check; sai -> reject (điểm #7)
    from setup_doctor.study.ground_truth import validate_ground_truth
    catalog_ids = {"a", "b", "c", "node.sdk.version"}
    bad = {"expected_failures": ["a", "node.sdk.version", "zz-not-a-check"]}
    errors = validate_ground_truth(bad, catalog_ids)
    assert "zz-not-a-check" in errors
    assert len(errors) == 1


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
# src/setup_doctor/study/ground_truth.py
from __future__ import annotations
import json


def validate_ground_truth(data: dict, catalog_ids: set[str]) -> list[str]:
    """Kiểm tra ground truth: mọi ID trong expected_failures/passes/root_causes
    phải thuộc catalog check. Trả về danh sách lỗi (rỗng = hợp lệ).

    (điểm #7 review) — ID ngoài catalog bị từ chối để universe luôn có ý nghĩa.
    """
    errors: list[str] = []
    for field in ("expected_failures", "expected_passes", "expected_root_causes"):
        for check_id in data.get(field, []) or []:
            if check_id not in catalog_ids:
                errors.append(f"{field}: unknown check_id '{check_id}' (not in catalog)")
    return errors


def load_ground_truth(path: str) -> dict:
    """Đọc 1 file ground truth JSON và validate cấu trúc cơ bản."""
    with open(path, encoding="utf-8") as f:
        data = json.load(f)
    for key in ("repo", "expected_failures"):
        if key not in data:
            raise ValueError(f"ground truth {path} thiếu field '{key}'")
    return data
```

```python
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
        # Registry chỉ chạy khi repo thật sự cần (giống runner.check) — tránh fail giả.
        target = set(ecosystems)
        if _registry_relevant(repo):
            target.add("registry")
        checkers = get_checkers(target) if target else []
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


def _registry_relevant(repo_path: str) -> bool:
    """Giống runner.run_check: registry only khi repo có .npmrc/pip.conf/.pypirc hoặc .git config."""
    for name in (".npmrc", "pip.conf", "pip.ini", ".pypirc"):
        if os.path.isfile(os.path.join(repo_path, name)):
            return True
    return os.path.isfile(os.path.join(repo_path, ".git", "config"))
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/unit/test_metrics.py -v`
Expected: 8 PASSED  # precision/recall/acc, recall_partial, missing_emit_fn, fp nuances, validate_gt, clarity x2

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
    # Output vẫn là JSON hợp lệ (machine-readable không bị phá vỡ)
    import json as _json
    _json.loads(res.stdout)


def test_cli_check_missing_path_exit_2(tmp_path):
    res = _run_cli(["check", str(tmp_path / "does-not-exist"), "--format", "json"])
    assert res.returncode == 2  # path không tồn tại -> lỗi input, KHÔNG phải no-ecosystem
    assert "invalid repo path" in res.stderr


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
import os
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


class RepoPathError(Exception):
    """Path không tồn tại / không phải thư mục -> exit 2 (lỗi input)."""


def _validate_repo_path(repo_path: str) -> None:
    if not os.path.exists(repo_path):
        raise RepoPathError(f"repo path does not exist: {repo_path}")
    if not os.path.isdir(repo_path):
        raise RepoPathError(f"repo path is not a directory: {repo_path}")


def _registry_relevant(repo_path: str) -> bool:
    """Registry checker chỉ chạy khi repo thật sự cần (có .npmrc/pip.conf/.pypirc hoặc remote git)."""
    for name in (".npmrc", "pip.conf", "pip.ini", ".pypirc"):
        if os.path.isfile(os.path.join(repo_path, name)):
            return True
    git_cfg = os.path.join(repo_path, ".git", "config")
    return os.path.isfile(git_cfg)


def run_check(repo_path: str, mode: str, config: ToolConfig, ai_enabled: bool = False) -> Report:
    _validate_repo_path(repo_path)
    os_name = detect_os()
    ecosystems = detect_ecosystems(repo_path)
    if not ecosystems:
        raise NoEcosystemError(repo_path)
    ctx = CheckContext(repo_path=repo_path, os=os_name, config=config)
    checks = []
    # Chỉ thêm registry khi repo thực sự cần (tránh fail giả về git user/SSH).
    target = set(ecosystems)
    if _registry_relevant(repo_path):
        target.add("registry")
    for checker in get_checkers(target):
        checks.extend(checker.run(ctx))
    report = diagnose(checks, mode, repo_path, os_name)
    if ai_enabled:
        _enhance_with_ai(report, config)
    return report


def _enhance_with_ai(report: Report, config: ToolConfig) -> None:
    from .ai.provider import get_provider, AIUnavailableError
    from .ai.remediation import AIRemediation
    from .ai.explainer import AIExplainer
    from .ai import AICallQuota
    try:
        provider = get_provider(config)
    except AIUnavailableError:
        return  # fallback: keep rule-based content only
    # Quota CHUNG cho remediation + explainer (NFR-9): không phải quota riêng mỗi phần.
    quota = AICallQuota(config.ai.max_requests)
    remediator = AIRemediation(provider, quota)
    for c in report.checks:
        if c.status.value == "fail":
            c.remediation = remediator.suggest(c, report.os)
    if report.diagnosis is not None:
        report.diagnosis.ai_explanation = AIExplainer(provider, quota).explain(report.diagnosis)
```

```python
# src/setup_doctor/cli.py
from __future__ import annotations
import argparse
import json
import sys
from . import __version__
from .config import load_config
from .output import render_text, render_json
from .runner import run_check, NoEcosystemError, RepoPathError
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
    # --ai ba trạng thái: None (không truyền) / True / --no-ai (False) — để config ai.enabled giữ nguyên khi không truyền.
    check_p.add_argument("--ai", dest="ai", action="store_true", default=None, help="enhance remediation/explanation with LLM")
    check_p.add_argument("--no-ai", dest="ai", action="store_false", help="disable AI even if config enables it")
    check_p.add_argument("--config", help="path to setup-doctor.toml")
    check_p.add_argument("--verbose", action="store_true")

    study_p = sub.add_parser("study", help="run repeatable flat-vs-dep research")
    study_p.add_argument("repos_file")
    study_p.add_argument("--ground-truth", help="JSON file or dir of ground-truth files")
    study_p.add_argument("--output-dir", default="research/output")
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)
    try:
        if args.command == "check":
            return _cmd_check(args)
        if args.command == "study":
            run_study(args.repos_file, args.ground_truth, args.output_dir)
            return 0
    except NoEcosystemError as exc:
        # Repo không hỗ trợ: exit 0, output đúng format đã chọn (kể cả JSON).
        _emit_no_ecosystem(args, exc.repo_path)
        return 0
    except RepoPathError as exc:
        print(f"setup-doctor: invalid repo path: {exc}", file=sys.stderr)
        return 2
    except KeyboardInterrupt:
        return 130
    except Exception as exc:  # internal tool error -> exit 2
        print(f"setup-doctor: internal error: {exc}", file=sys.stderr)
        if getattr(args, "verbose", False):
            import traceback
            traceback.print_exc()
        return 2
    return 2


def _emit_no_ecosystem(args, repo_path: str) -> None:
    """No-ecosystem: vẫn tôn trọng --format json để không phá vỡ machine-readable."""
    fmt = getattr(args, "format", None)
    if fmt == "json":
        payload = json.dumps({
            "schema_version": "1.0",
            "repo_path": repo_path,
            "message": "no supported ecosystem detected",
            "exit_code": 0,
        }, indent=2)
        print(payload)
    else:
        print(f"no supported ecosystem detected for {repo_path}")


def _cmd_check(args) -> int:
    config = load_config(path=args.config, search_from=args.repo_path, overrides={
        "mode": args.mode,
        "format": args.format,
        "ai": args.ai,
    })
    mode = args.mode or config.default_mode
    report = run_check(args.repo_path, mode, config, ai_enabled=bool(config.ai.enabled))
    use_json = args.format == "json" or (args.format is None and config.output_format == "json")
    if use_json:
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
setup-doctor check <repo> --format json --output report.json  # ghi JSON ra file
setup-doctor check <repo> --fix            # áp dụng remediation an toàn (có backup)
setup-doctor check <repo> --ai             # tăng cường AI (cần SETUP_DOCTOR_API_KEY)
setup-doctor study repos.txt --ground-truth research/ground_truth --output-dir research/output
setup-doctor --version
```

Exit codes: `0` pass/không-ecosystem, `1` có lỗi (severity error), `2` lỗi nội bộ hoặc path không tồn tại.

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

## Self-Review Checklist (coverage mapping — sửa sau khi viết; KHÔNG phải kết quả test)

> **Lưu ý:** đây là bản đồ **coverage** (task nào phủ yêu cầu nào), chưa phải xác nhận "đã pass". Mọi AC chỉ được đánh dấu hoàn thành sau khi code tồn tại và test chạy thật (executing-plans/subagent-driven-development sẽ xác minh).

**Spec coverage:**
- FR-1 (ecosystem detect) → Task 4
- FR-2 (SDK version) → Tasks 5-8
- FR-3 (deps) → Tasks 5, 6, 7, 8
- FR-4 (services) → Task 9
- FR-5 (registry/credentials, không đọc nội dung) → Task 10
- FR-6 (2 modes cùng bộ check) → Tasks 11, 12 (engine nhận cùng `checks`)
- FR-7 (JSON + exit codes) → Tasks 13, 18
- FR-8 (exact remediation steps) → mọi checker có `RemediationStep(step, command)`
- FR-9 (--fix backup/log) → Task 14
- FR-10 (study) → Task 17
- FR-11 (không tự sửa khi không --fix) → checkers luôn read-only; fixer chỉ chạy khi `--fix`
- FR-12/13 (AI remediation/explainer + fallback) → Tasks 15, 16
- FR-14 (study rule-based) → `run_study` không gọi AI
- FR-15 (config file) → Task 3
- NFR-3 (timeout 30s) → `run_command` default timeout=30
- NFR-5 (Windows-first) → `detect_os` + `_WHITELIST_OP` argv theo OS
- AC-1..AC-10 → map tới test tương ứng (AC-x có test đặt tên tương ứng trong mỗi task)

**Placeholder scan:** không có "TBD"/"TODO" trong plan trước khi chạy; mọi bước đều có code đầy đủ. (Nếu trong lúc thực thi phát hiện thiếu → sửa plan trước khi code.)

**Type consistency:** `CheckResult(status=CheckStatus.X)` dùng enum nhất quán; `run_command` luôn trả `CommandResult`; `Fixer.apply(report) -> FixReport`; `main() -> int`; `compute_metrics(report, gt) -> dict`; `AIRemediation(provider, quota)` / `AIExplainer(provider, quota)`; `diagnose(checks, mode, repo_path, os_name)` — khớp giữa các task.