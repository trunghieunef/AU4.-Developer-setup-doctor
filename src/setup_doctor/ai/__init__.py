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