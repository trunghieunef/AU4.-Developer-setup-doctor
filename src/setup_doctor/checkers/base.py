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