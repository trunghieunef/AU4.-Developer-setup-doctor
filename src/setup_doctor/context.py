# src/setup_doctor/context.py
from __future__ import annotations
from dataclasses import dataclass, field


@dataclass
class CheckContext:
    repo_path: str
    os: str
    config: object = None
    results: dict[str, object] = field(default_factory=dict)