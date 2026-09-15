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

        pypi = next((os.path.join(ctx.repo_path, name)
                     for name in ("pip.conf", "pip.ini")
                     if os.path.isfile(os.path.join(ctx.repo_path, name))), None)
        if pypi:
            py = which("py") or which("python")
            results.append(CheckResult(
                check_id="registry.pypi", name="pip index file present",
                ecosystem=self.ecosystem,
                status=CheckStatus.PASS if py else CheckStatus.SKIP,
                evidence=f"{os.path.basename(pypi)} exists" if py else "python not found",
                remediation=[RemediationStep("Point pip at the required index",
                                             "pip config set global.index-url <url>", safe_fix=False)],
            ))
        else:
            results.append(CheckResult(
                check_id="registry.pypi", name="pip index file present",
                ecosystem=self.ecosystem, status=CheckStatus.SKIP,
                evidence="no pip.conf/pip.ini in repo",
            ))
        return results