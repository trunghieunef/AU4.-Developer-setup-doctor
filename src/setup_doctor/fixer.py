# src/setup_doctor/fixer.py
from __future__ import annotations
import datetime
import os
import shutil
from dataclasses import dataclass, field
from .models import Report
from .utils.commands import run_command


class OperationNotAllowedError(Exception):
    """Op không nằm trong whitelist fix (không được tự chạy)."""


# Whitelist op: chỉ những op này mới được tự chạy khi --fix.
# - argv: lệnh thực thi (list, KHÔNG shell operator).
# - reversible: True = có thể rollback bằng backup file (chỉ áp dụng cho file
#   cấu hình nhỏ đã khai báo); False = KHÔNG thể rollback (install/restore/
#   start-service/cache toàn cục) — chỉ log rõ, không hứa khôi phục.
# - timeout: riêng cho op fix (npm ci/mvn resolve/dotnet restore có thể lâu);
#   KHÔNG ràng buộc bởi NFR-3 (30s cho lệnh check).
_WHITELIST_OP: dict[str, dict] = {
    "install-node-deps":  {"argv": ["npm", "ci"], "reversible": False, "timeout": 180},
    "install-yarn-deps":  {"argv": ["yarn", "install", "--frozen-lockfile"], "reversible": False, "timeout": 180},
    "create-venv":        {"argv": ["py", "-m", "venv", ".venv"], "reversible": False, "timeout": 60},
    "install-python-deps":{"argv": ["pip", "install", "-r", "requirements.txt"], "reversible": False, "timeout": 180},
    "resolve-java-deps":  {"argv": ["mvn", "dependency:resolve"], "reversible": False, "timeout": 300},
    "restore-dotnet":     {"argv": ["dotnet", "restore"], "reversible": False, "timeout": 300},
    "start-service":      {"argv": ["docker", "compose", "up", "-d"], "reversible": False, "timeout": 180},
    "create-env":         {"argv": None, "reversible": True, "timeout": 5},  # Python: copy .env.example -> .env
    "restore-lockfile":   {"argv": ["npm", "install", "--package-lock-only"], "reversible": False, "timeout": 120},
    "enable-corepack":    {"argv": ["corepack", "enable"], "reversible": False, "timeout": 60},
    "start-docker":       {"argv": ["start", "", r"C:\Program Files\Docker\Docker\Docker Desktop.exe"],
                           "reversible": False, "timeout": 30,
                           "note": "Windows-only; Linux/macOS roadmap"},
}


@dataclass
class FixLogEntry:
    command: str
    status: str  # applied | skipped | failed | rolled_back
    operation: str = ""
    detail: str = ""
    reversible: bool = False


@dataclass
class FixReport:
    backup_dir: str
    entries: list[FixLogEntry] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "backup_dir": self.backup_dir,
            "entries": [{"command": e.command, "status": e.status,
                         "operation": e.operation, "detail": e.detail,
                         "reversible": e.reversible} for e in self.entries],
        }


class Fixer:
    BACKUP_DIR_NAME = ".setup-doctor-backup"

    def __init__(self, repo_path: str):
        self.repo_path = os.path.abspath(repo_path)
        # Timestamp đủ phân giải (microsecond) để tránh trùng khi chạy 2 lần nhanh.
        stamp = datetime.datetime.now().strftime("%Y%m%d-%H%M%S-%f")
        self.backup_dir = os.path.join(self.repo_path, self.BACKUP_DIR_NAME, stamp)

    def _is_inside_repo(self, rel: str) -> bool:
        """Chặn path traversal: file khai báo phải nằm trong repo."""
        full = os.path.normpath(os.path.join(self.repo_path, rel))
        return os.path.commonpath([self.repo_path, full]) == self.repo_path

    def _backup_file(self, rel: str) -> None:
        src = os.path.join(self.repo_path, rel)
        if not os.path.exists(src):
            return
        dst = os.path.join(self.backup_dir, rel)
        os.makedirs(os.path.dirname(dst), exist_ok=True)
        shutil.copy2(src, dst)

    def _restore_file(self, rel: str) -> None:
        """Khôi phục file từ backup; nếu file do fix tạo mới (không backup) -> xóa đi."""
        dst = os.path.join(self.backup_dir, rel)
        target = os.path.join(self.repo_path, rel)
        if os.path.exists(dst):
            os.makedirs(os.path.dirname(target), exist_ok=True)
            shutil.copy2(dst, target)
        else:
            if os.path.exists(target):
                os.remove(target)

    def _apply_create_env(self, entry: FixLogEntry) -> None:
        """create-env (reversible): copy .env.example -> .env bằng Python."""
        example = os.path.join(self.repo_path, ".env.example")
        target = os.path.join(self.repo_path, ".env")
        if not os.path.isfile(example):
            entry.status = "failed"
            entry.detail = ".env.example missing"
            return
        try:
            with open(example, encoding="utf-8") as f:
                content = f.read()
            with open(target, "w", encoding="utf-8") as f:
                f.write(content)
            entry.status = "applied"
        except OSError as exc:
            entry.status = "failed"
            entry.detail = str(exc)

    def _apply_step(self, step, entry: FixLogEntry) -> None:
        # 1) Kiểm tra toàn bộ file khai báo nằm trong repo (chống path traversal).
        for rel in step.files:
            if not self._is_inside_repo(rel):
                entry.status = "skipped"
                entry.detail = f"path outside repo: {rel}"
                return
        # 2) Backup các file khai báo (chỉ file cấu hình nhỏ, đã kiểm tra trong repo).
        for rel in step.files:
            self._backup_file(rel)
        # 3) Thực thi theo operation whitelist.
        op = _WHITELIST_OP.get(step.operation)
        if op is None:
            entry.status = "skipped"
            entry.detail = f"operation not allowed: {step.operation}"
            return
        if step.operation == "create-env":
            self._apply_create_env(entry)
            return
        res = run_command(op["argv"], cwd=self.repo_path, timeout=op["timeout"])
        if res.ok:
            entry.status = "applied"
        else:
            entry.status = "failed"
            entry.detail = res.stderr or "command failed"
            if not op["reversible"]:
                entry.detail += "; non-reversible operation: rollback unavailable"

    def apply(self, report: Report) -> FixReport:
        os.makedirs(self.backup_dir, exist_ok=True)
        fix_report = FixReport(backup_dir=self.backup_dir)
        applied_reversible: list[tuple] = []  # các bước reversible đã apply -> có thể rollback
        for c in report.checks:
            if c.status.value != "fail":
                continue
            for step in c.remediation:
                op = _WHITELIST_OP.get(step.operation or "")
                entry = FixLogEntry(
                    command=step.command or (op["argv"][0] if op and op["argv"] else ""),
                    status="skipped",
                    operation=step.operation or "",
                    reversible=bool(op and op["reversible"]),
                )
                if not step.safe_fix or step.source != "manual" or step.operation is None:
                    entry.detail = "not safe_fix / not manual / no operation"
                else:
                    self._apply_step(step, entry)
                    if entry.status == "applied":
                        if entry.reversible:
                            applied_reversible.append((step, entry))
                    elif entry.status == "failed":
                        # Transaction: rollback các bước REVERSIBLE đã apply.
                        # Các op non-reversible (npm ci/mvn/docker) ĐÃ CHẠY THÀNH CÔNG
                        # trước đó không thể khôi phục — chỉ ghi rõ trong log.
                        for prev_step, prev_entry in applied_reversible:
                            for rel in prev_step.files:
                                self._restore_file(rel)
                            prev_entry.status = "rolled_back"
                        applied_reversible.clear()
                fix_report.entries.append(entry)
                if entry.status == "failed":
                    # Dừng toàn bộ nếu có bước fail (tránh chồng thêm lỗi).
                    return fix_report
        return fix_report