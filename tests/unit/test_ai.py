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