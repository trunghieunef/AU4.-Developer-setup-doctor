# src/setup_doctor/models.py
from __future__ import annotations
from dataclasses import dataclass, field
from enum import Enum


class CheckStatus(str, Enum):
    PASS = "pass"
    FAIL = "fail"
    SKIP = "skip"


class Severity(str, Enum):
    ERROR = "error"
    WARNING = "warning"
    INFO = "info"


@dataclass
class RemediationStep:
    step: str
    command: str = ""                    # display_command cho người dùng (vd "npm ci")
    safe_fix: bool = False
    source: str = "manual"
    files: list[str] = field(default_factory=list)  # repo-relative files để backup trước khi run
    operation: str | None = None         # whitelist op key ("install-node-deps", "create-env"...); None = chỉ hiển thị, KHÔNG tự fix
    argv: list[str] | None = None        # argv list cụ thể cho op (ưu tiên hơn command khi fix)

    def to_dict(self) -> dict:
        return {
            "step": self.step,
            "command": self.command,
            "safe_fix": self.safe_fix,
            "source": self.source,
            "files": list(self.files),
            "operation": self.operation,
            "argv": list(self.argv) if self.argv is not None else None,
        }


@dataclass
class CheckResult:
    check_id: str
    name: str
    ecosystem: str
    severity: Severity = Severity.ERROR
    status: CheckStatus = CheckStatus.PASS
    evidence: str = ""
    remediation: list[RemediationStep] = field(default_factory=list)
    depends_on: list[str] = field(default_factory=list)
    caused_by: str | None = None         # dep mode: primary root cause (first)
    causes: list[str] = field(default_factory=list)  # dep mode: TẤT CẢ root causes gây ra check này

    def to_dict(self) -> dict:
        return {
            "check_id": self.check_id,
            "name": self.name,
            "ecosystem": self.ecosystem,
            "severity": self.severity.value,
            "status": self.status.value,
            "evidence": self.evidence,
            "remediation": [r.to_dict() for r in self.remediation],
            "depends_on": list(self.depends_on),
            "caused_by": self.caused_by,
            "causes": list(self.causes),
        }


@dataclass
class RootCause:
    cause_check_id: str
    message: str
    affected_checks: list[str]
    chain: str

    def to_dict(self) -> dict:
        return {
            "cause_check_id": self.cause_check_id,
            "message": self.message,
            "affected_checks": list(self.affected_checks),
            "chain": self.chain,
        }


@dataclass
class Diagnosis:
    root_causes: list[RootCause] = field(default_factory=list)
    ai_explanation: str | None = None

    def to_dict(self) -> dict:
        return {
            "root_causes": [rc.to_dict() for rc in self.root_causes],
            "ai_explanation": self.ai_explanation,
        }


@dataclass
class Report:
    schema_version: str = "1.0"
    repo_path: str = ""
    os: str = ""
    mode: str = "dep"
    generated_at: str = ""
    summary: dict = field(default_factory=dict)
    checks: list[CheckResult] = field(default_factory=list)
    diagnosis: Diagnosis | None = None
    exit_code: int = 0

    def to_dict(self) -> dict:
        d = {
            "schema_version": self.schema_version,
            "repo_path": self.repo_path,
            "os": self.os,
            "mode": self.mode,
            "generated_at": self.generated_at,
            "summary": dict(self.summary),
            "checks": [c.to_dict() for c in self.checks],
        }
        if self.diagnosis is not None:
            d["diagnosis"] = self.diagnosis.to_dict()
        d["exit_code"] = self.exit_code
        return d