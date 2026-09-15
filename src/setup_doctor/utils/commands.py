# src/setup_doctor/utils/commands.py
from __future__ import annotations
import shutil
import subprocess
import sys
from dataclasses import dataclass


@dataclass
class CommandResult:
    returncode: int
    stdout: str
    stderr: str

    @property
    def ok(self) -> bool:
        return self.returncode == 0


def which(name: str) -> str | None:
    return shutil.which(name)


def _resolve_cmd_win(cmd: list[str]) -> list[str]:
    """Trên Windows, script .cmd/.bat KHÔNG chạy được trực tiếp qua CreateProcess
    (shell=False) -> phải bọc qua ``cmd.exe /c``.

    Phát hiện thật khi test: ``npm`` (npm.cmd), ``yarn``, ``mvn``, ``corepack``
    đều là .cmd trên Windows nên whitelist fix op sẽ fail nếu không xử lý.
    """
    if sys.platform != "win32":
        return cmd
    exe = shutil.which(cmd[0])
    if exe and exe.lower().endswith((".cmd", ".bat")):
        return ["cmd", "/c", *cmd]
    return cmd


def _run(cmd: list[str], cwd: str | None, timeout: int, env: dict | None) -> CommandResult:
    creationflags = subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0
    cmd = _resolve_cmd_win(cmd)
    proc = subprocess.run(
        cmd, cwd=cwd, capture_output=True, text=True,
        timeout=timeout, env=env, creationflags=creationflags,
    )
    return CommandResult(proc.returncode, proc.stdout.strip(), proc.stderr.strip())


def run_command(cmd: list[str], cwd: str | None = None, timeout: int = 30, env: dict | None = None) -> CommandResult:
    try:
        return _run(cmd, cwd=cwd, timeout=timeout, env=env)
    except subprocess.TimeoutExpired:
        return CommandResult(-1, "", f"Command timed out after {timeout}s: {' '.join(cmd)}")
    except FileNotFoundError:
        return CommandResult(-1, "", f"Command not found: {cmd[0]}")
    except OSError as exc:
        return CommandResult(-1, "", f"OS error running {cmd[0]}: {exc}")