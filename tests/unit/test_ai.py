# tests/unit/test_ai.py
import os
import pytest
from setup_doctor.ai.provider import AIProvider, AIUnavailableError, get_provider
from setup_doctor.config import AIConfig, ToolConfig


def test_get_provider_requires_key(monkeypatch):
    monkeypatch.delenv("SETUP_DOCTOR_API_KEY", raising=False)
    with pytest.raises(AIUnavailableError):
        get_provider(ToolConfig())


def test_get_provider_returns_openai_client(monkeypatch):
    monkeypatch.setenv("SETUP_DOCTOR_API_KEY", "sk-test")
    cfg = ToolConfig(ai=AIConfig(provider="openai"))
    provider = get_provider(cfg)
    from setup_doctor.ai.provider import OpenAIClient
    assert isinstance(provider, OpenAIClient)
    assert provider.model == "gpt-4o-mini"


def test_fake_provider_contract():
    class FakeProvider(AIProvider):
        def __init__(self, data):
            self.data = data
        def complete(self, system, user, response_schema):
            return self.data

    fp = FakeProvider({"suggestions": []})
    assert fp.complete("s", "u", dict) == {"suggestions": []}


# ---------------- Remediation + explainer ----------------
from setup_doctor.ai.provider import AIUnavailableError
from setup_doctor.ai.remediation import AIRemediation
from setup_doctor.ai.explainer import AIExplainer
from setup_doctor.models import CheckResult, CheckStatus, RemediationStep, Diagnosis, RootCause


def _quota(n=100):
    from setup_doctor.ai import AICallQuota
    return AICallQuota(n)


class FakeProvider(AIProvider):
    def __init__(self, data, error=False):
        self.data = data
        self.error = error
    def complete(self, system, user, response_schema):
        if self.error:
            raise AIUnavailableError("offline")
        return self.data


def test_ai_remediation_appends_suggestions_after_manual():
    manual = [RemediationStep("Install Node", "nvm install 22", safe_fix=False)]
    cr = CheckResult("sdk", "SDK", "node", status=CheckStatus.FAIL, evidence="18 < 20",
                     remediation=manual)
    provider = FakeProvider({"suggestions": [{"step": "Upgrade node", "command": "nvm install 20"}]})
    steps = AIRemediation(provider, _quota()).suggest(cr, "windows")
    assert steps[0].command == "nvm install 22"      # manual first
    assert steps[-1].source == "ai"
    assert steps[-1].safe_fix is False


def test_ai_remediation_falls_back_on_error():
    cr = CheckResult("sdk", "SDK", "node", status=CheckStatus.FAIL, evidence="18 < 20",
                     remediation=[RemediationStep("Install Node", "nvm install 22")])
    steps = AIRemediation(FakeProvider(None, error=True), _quota()).suggest(cr, "windows")
    assert len(steps) == 1
    assert steps[0].command == "nvm install 22"


def test_ai_remediation_honors_shared_quota():
    cr = CheckResult("sdk", "SDK", "node", status=CheckStatus.FAIL, evidence="18 < 20",
                     remediation=[RemediationStep("Install Node", "nvm install 22")])
    quota = _quota(1)  # chỉ cho phép 1 AI call
    steps1 = AIRemediation(FakeProvider({"suggestions": []}), quota).suggest(cr, "windows")
    steps2 = AIRemediation(FakeProvider({"suggestions": []}), quota).suggest(cr, "windows")
    assert quota.remaining == 0
    assert len(steps2) == 1  # call thứ 2 bị chặn -> chỉ còn manual


def test_ai_remediation_sanitizes_evidence():
    manual = [RemediationStep("Install Node", "nvm install 22", safe_fix=False)]
    cr = CheckResult("sdk", "SDK", "node", status=CheckStatus.FAIL,
                     evidence="C:\\Users\\alice\\repo\nhttps://registry.example.com/npm\nsk-abc123secret",
                     remediation=manual)
    captured = {}
    class Recorder(AIProvider):
        def complete(self, system, user, response_schema):
            captured["user"] = user
            return {"suggestions": []}
    AIRemediation(Recorder(), _quota()).suggest(cr, "windows")
    assert "C:\\Users\\alice" not in captured["user"]
    assert "registry.example.com" not in captured["user"]
    assert "sk-abc123secret" not in captured["user"]


def test_ai_remediation_validates_schema_and_falls_back():
    cr = CheckResult("sdk", "SDK", "node", status=CheckStatus.FAIL, evidence="18 < 20",
                     remediation=[RemediationStep("Install Node", "nvm install 22")])
    class BadProvider(AIProvider):
        def complete(self, system, user, response_schema):
            return {"suggestions": [{"step": "x"}]}  # thiếu command -> invalid
    steps = AIRemediation(BadProvider(), _quota()).suggest(cr, "windows")
    assert len(steps) == 1
    assert steps[0].command == "nvm install 22"  # fallback manual


def test_ai_explainer_returns_text():
    diag = Diagnosis(root_causes=[RootCause("sdk", "msg", ["a"], "a → b")])
    provider = FakeProvider({"explanation": "Vì SDK thiếu nên deps không cài được."})
    assert AIExplainer(provider, _quota()).explain(diag) == "Vì SDK thiếu nên deps không cài được."


def test_ai_explainer_none_on_error():
    diag = Diagnosis(root_causes=[RootCause("sdk", "msg", ["a"], "a → b")])
    assert AIExplainer(FakeProvider(None, error=True), _quota()).explain(diag) is None