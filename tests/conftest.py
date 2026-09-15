# tests/conftest.py
import json
import pytest
from setup_doctor.utils.commands import CommandResult


class FakeRunner:
    """Deterministic stand-in for run_command; keyed by command tuple."""
    def __init__(self):
        self.scripts: dict[tuple, CommandResult] = {}
        self.calls: list[list[str]] = []

    def set(self, cmd: list[str], result: CommandResult) -> None:
        self.scripts[tuple(cmd)] = result

    def __call__(self, cmd, cwd=None, timeout=30, env=None):
        self.calls.append(list(cmd))
        return self.scripts.get(tuple(cmd), CommandResult(0, "", ""))


@pytest.fixture
def fake_runner():
    return FakeRunner()


def write_json(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data), encoding="utf-8")