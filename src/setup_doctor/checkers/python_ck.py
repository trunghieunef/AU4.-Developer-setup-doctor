# src/setup_doctor/checkers/python_ck.py
from __future__ import annotations
import os
import re
from .base import Checker
from ..models import CheckResult, RemediationStep, CheckStatus, Severity
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
                                argv=["py", "-m", "venv", ".venv"], files=[]),
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