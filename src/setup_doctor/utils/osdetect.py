# src/setup_doctor/utils/osdetect.py
from __future__ import annotations
import platform
import sys


def detect_os() -> str:
    system = platform.system().lower()
    if system == "windows":
        return "windows"
    if system == "darwin":
        return "macos"
    if system == "linux":
        return "linux"
    return sys.platform