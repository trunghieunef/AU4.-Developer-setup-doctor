# src/setup_doctor/registry.py
from __future__ import annotations
import os
from importlib import metadata

_CHECK_MARKERS = {
    "node": ("package.json",),
    "python": ("pyproject.toml", "requirements.txt", "setup.py", "setup.cfg", "Pipfile"),
    "java": ("pom.xml", "build.gradle", "build.gradle.kts", "settings.gradle"),
    "dotnet": ("*.sln", "*.csproj", "global.json"),
    "services": ("docker-compose.yml", "docker-compose.yaml", "compose.yml", "compose.yaml", ".env.example"),
}

_SKIP_DIRS = {"node_modules", "venv", ".venv", "__pycache__", ".git", ".idea", ".vscode"}

# Plugin-style: checker đăng ký qua entry points group "setup_doctor.checkers".
# Thêm checker mới = thêm 1 module + khai báo entry point trong pyproject.toml,
# không cần sửa registry.py. (NFR-4)
_ENTRY_POINT_GROUP = "setup_doctor.checkers"


def _matches(name: str, pattern: str) -> bool:
    if "*" in pattern:
        return name.endswith(pattern.lstrip("*"))
    return name == pattern


def detect_ecosystems(repo_path: str) -> set[str]:
    """Scan the repo (pruning vendor dirs) and return detected ecosystems."""
    found: set[str] = set()
    for root, dirs, files in os.walk(repo_path):
        dirs[:] = sorted(d for d in dirs if d not in _SKIP_DIRS)
        for fname in files:
            for eco, patterns in _CHECK_MARKERS.items():
                if eco in found:
                    continue
                if any(_matches(fname, p) for p in patterns):
                    found.add(eco)
    return found


def _load_checker_classes() -> list[type]:
    """Nạp tất cả checker class đã đăng ký qua entry points.

    Fallback: nếu entry points rỗng (vd chạy unit test trước khi cài editable,
    hoặc môi trường không có metadata) → import trực tiếp danh sách built-in,
    để test/CLI vẫn chạy được (điểm review "entry point plugin").
    """
    try:
        eps = metadata.entry_points(group=_ENTRY_POINT_GROUP) if hasattr(metadata, "entry_points") else metadata.entry_points().select(group=_ENTRY_POINT_GROUP)
        classes = [ep.load() for ep in eps]
        if classes:
            return classes
    except Exception:
        pass  # fallback bên dưới
    from .checkers.node import NodeChecker
    from .checkers.python_ck import PythonChecker
    from .checkers.java import JavaChecker
    from .checkers.dotnet_ck import DotnetChecker
    from .checkers.services import ServicesChecker
    from .checkers.registry import RegistryChecker
    return [NodeChecker, PythonChecker, JavaChecker, DotnetChecker,
            ServicesChecker, RegistryChecker]


def get_checkers(ecosystems: set[str]) -> list:
    all_checkers = [cls() for cls in _load_checker_classes()]
    return [c for c in all_checkers if c.ecosystem in ecosystems]