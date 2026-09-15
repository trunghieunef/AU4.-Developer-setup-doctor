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