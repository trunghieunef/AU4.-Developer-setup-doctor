# src/setup_doctor/ai/provider.py
from __future__ import annotations
import json
import os
from ..config import ToolConfig


class AIUnavailableError(Exception):
    """Raised when the LLM cannot be reached or has no API key."""


class AIProvider:
    def complete(self, system: str, user: str, response_schema: type) -> dict | None:
        raise NotImplementedError


class OpenAIClient(AIProvider):
    def __init__(self, api_key: str, model: str = "gpt-4o-mini", timeout_sec: int = 20):
        self._api_key = api_key
        self.model = model
        self._timeout_sec = timeout_sec

    def complete(self, system: str, user: str, response_schema: type) -> dict | None:
        try:
            from openai import OpenAI
        except ImportError as exc:
            raise AIUnavailableError("openai package not installed (pip install setup-doctor[ai])") from exc
        try:
            client = OpenAI(api_key=self._api_key, timeout=self._timeout_sec)
            resp = client.chat.completions.create(
                model=self.model,
                messages=[{"role": "system", "content": system},
                          {"role": "user", "content": user}],
                response_format={"type": "json_object"},
            )
            return json.loads(resp.choices[0].message.content)
        except Exception as exc:  # network, auth, rate limit, malformed JSON
            raise AIUnavailableError(str(exc)) from exc


class AnthropicClient(AIProvider):
    def __init__(self, api_key: str, model: str = "claude-3-5-haiku-latest", timeout_sec: int = 20):
        self._api_key = api_key
        self.model = model
        self._timeout_sec = timeout_sec

    def complete(self, system: str, user: str, response_schema: type) -> dict | None:
        try:
            from anthropic import Anthropic
        except ImportError as exc:
            raise AIUnavailableError("anthropic package not installed (pip install setup-doctor[ai])") from exc
        try:
            client = Anthropic(api_key=self._api_key, timeout=self._timeout_sec)
            resp = client.messages.create(
                model=self.model,
                max_tokens=500,
                system=system,
                messages=[{"role": "user", "content": user}],
            )
            return json.loads(resp.content[0].text)
        except Exception as exc:
            raise AIUnavailableError(str(exc)) from exc


def get_provider(cfg: ToolConfig, api_key: str | None = None) -> AIProvider:
    api_key = api_key or os.environ.get("SETUP_DOCTOR_API_KEY")
    if not api_key:
        raise AIUnavailableError("Missing API key; set SETUP_DOCTOR_API_KEY")
    if cfg.ai.provider == "anthropic":
        return AnthropicClient(api_key, model=cfg.ai.model, timeout_sec=cfg.ai.timeout_sec)
    return OpenAIClient(api_key, model=cfg.ai.model, timeout_sec=cfg.ai.timeout_sec)