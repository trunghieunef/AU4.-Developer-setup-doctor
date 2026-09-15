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

    def __init__(self):
        self._pkg_parse_error = None

    def _read_json(self, repo, name):
        path = os.path.join(repo, name)
        if not os.path.isfile(path):
            return None
        try:
            with open(path, encoding="utf-8") as f:
                return json.load(f)
        except json.JSONDecodeError as exc:
            # Ghi lại lỗi parse để emit check node.package_json.valid (M2 — không silent fail).
            self._pkg_parse_error = f"{name} JSON error: {exc}"
            return None
        except OSError as exc:
            self._pkg_parse_error = f"{name} read error: {exc}"
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
        # M2: nếu package.json tồn tại nhưng JSON lỗi -> báo FAIL thay vì silent pass.
        self._pkg_parse_error = None
        self._read_json(ctx.repo_path, "package.json")
        if self._pkg_parse_error:
            results.append(CheckResult(
                check_id="node.package_json.valid", name="package.json valid JSON",
                ecosystem=self.ecosystem, status=CheckStatus.FAIL,
                evidence=self._pkg_parse_error,
                remediation=[RemediationStep("Fix package.json syntax", "", safe_fix=False)],
            ))

        node_exe = which("node")
        present = node_exe is not None
        version = ""
        version_ok = True
        if present:
            res = run_command([node_exe, "--version"], timeout=10)
            version = res.stdout
            version_ok = res.ok and bool(version)  # exe có trong PATH nhưng --version fail -> FAIL (#5)
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
        # npm thiếu trong repo Node -> FAIL (prerequisite thiếu), không phải SKIP (#5)
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