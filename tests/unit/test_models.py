# tests/unit/test_models.py
from setup_doctor.models import (
    CheckResult, RemediationStep, Report, Diagnosis, RootCause,
    CheckStatus, Severity,
)

def test_check_result_to_dict_uses_enum_values():
    cr = CheckResult(
        check_id="node.sdk.version",
        name="Node.js SDK version",
        ecosystem="node",
        severity=Severity.ERROR,
        status=CheckStatus.FAIL,
        evidence="Node v18.16.0 found",
        remediation=[RemediationStep("Install Node 22", "nvm install 22", safe_fix=True)],
        depends_on=["node.runtime.present"],
    )
    d = cr.to_dict()
    assert d["check_id"] == "node.sdk.version"
    assert d["severity"] == "error"          # enum value, not enum object
    assert d["status"] == "fail"
    assert d["caused_by"] is None
    assert d["causes"] == []
    assert d["remediation"][0] == {
        "step": "Install Node 22",
        "command": "nvm install 22",
        "safe_fix": True,
        "source": "manual",
        "files": [],
        "operation": None,
        "argv": None,
    }


def test_remediation_step_with_operation_and_argv():
    step = RemediationStep("Install deps", "npm ci", safe_fix=True,
                           operation="install-node-deps", argv=["npm", "ci"])
    d = step.to_dict()
    assert d["operation"] == "install-node-deps"
    assert d["argv"] == ["npm", "ci"]


def test_report_to_dict_nested_objects():
    rc = RootCause("node.sdk.version", "msg", ["a", "b"], "a → b")
    report = Report(
        repo_path="/repo", os="windows", mode="dep",
        summary={"total": 1, "pass": 0, "fail": 1, "skip": 0, "warnings": 0},
        checks=[CheckResult("a", "A", "node", status=CheckStatus.FAIL)],
        diagnosis=Diagnosis(root_causes=[rc]),
        exit_code=1,
    )
    d = report.to_dict()
    assert d["schema_version"] == "1.0"
    assert d["diagnosis"]["root_causes"][0]["cause_check_id"] == "node.sdk.version"
    assert d["exit_code"] == 1