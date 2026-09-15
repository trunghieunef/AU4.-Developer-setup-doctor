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