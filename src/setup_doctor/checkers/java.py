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
        # (#6): chỉ báo warning, không PASS; thiếu cache -> FAIL (gợi ý --fix resolve).
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

        # Read-only: build file (pom.xml/build.gradle) phải tồn tại (không chạy build).
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