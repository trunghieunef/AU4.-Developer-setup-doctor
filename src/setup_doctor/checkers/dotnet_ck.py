# src/setup_doctor/checkers/dotnet_ck.py
from __future__ import annotations
import json
import os
from .base import Checker
from ..models import CheckResult, RemediationStep, CheckStatus, Severity
from ..utils.commands import run_command, which


def _nuget_cache_ok() -> bool:
    return os.path.isdir(os.path.join(os.path.expanduser("~"), ".nuget", "packages"))


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

        # Read-only: chỉ stat NuGet cache. Cache tồn tại KHÔNG chứng minh deps repo sẵn sàng (#6)
        # -> warning khi có cache (pass với severity warning), FAIL khi thiếu.
        cache_ok = _nuget_cache_ok()
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

        # Read-only: kiểm tra build file tồn tại ở repo root
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