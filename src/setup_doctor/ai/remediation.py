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
_PATH_RE = re.compile(r"[A-Za-z]:\\[^\s\"']+|[A-Za-z]:/[^\s\"']+|/[\w.\-/]+/[\w.\-]+")
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
        self.failures = 0

    def suggest(self, check: CheckResult, os_name: str) -> list[RemediationStep]:
        manual = list(check.remediation)
        if not self._quota.take():
            return manual
        user = (f"OS: {os_name}\ncheck_id: {check.check_id}\n"
                f"evidence: {sanitize(check.evidence)}\n")
        try:
            data = self._provider.complete(_SYSTEM_PROMPT, user, dict)
        except Exception:
            self.failures += 1
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
