# src/setup_doctor/config.py
from __future__ import annotations
import os
import tomllib
from dataclasses import dataclass, field


@dataclass
class AIConfig:
    enabled: bool = False
    provider: str = "openai"       # openai | anthropic
    model: str = "gpt-4o-mini"
    max_requests: int = 10
    timeout_sec: int = 20
    api_key: str | None = None


@dataclass
class ToolConfig:
    default_mode: str = "dep"      # flat | dep
    output_format: str = "text"    # text | json
    ai: AIConfig = field(default_factory=AIConfig)


def load_config(
    path: str | None = None,
    overrides: dict | None = None,
    search_from: str | os.PathLike | None = None,
) -> ToolConfig:
    cfg = ToolConfig()
    # Tự tìm config: path truyền rõ -> cwd/repo root -> home
    resolved_path = _resolve_config_path(path, search_from)
    if resolved_path and os.path.isfile(resolved_path):
        with open(resolved_path, "rb") as f:
            data = tomllib.load(f)
        mode = data.get("mode", {})
        cfg.default_mode = mode.get("default", cfg.default_mode)
        out = data.get("output", {})
        cfg.output_format = out.get("format", cfg.output_format)
        ai = data.get("ai", {})
        cfg.ai.enabled = ai.get("enabled", cfg.ai.enabled)
        cfg.ai.provider = ai.get("provider", cfg.ai.provider)
        cfg.ai.model = ai.get("model", cfg.ai.model)
        cfg.ai.max_requests = ai.get("max_requests", cfg.ai.max_requests)
        cfg.ai.timeout_sec = ai.get("timeout_sec", cfg.ai.timeout_sec)
    dotenv = _load_dotenv(_resolve_dotenv_path(resolved_path))

    def setting(name: str, default: str | None = None) -> str | None:
        return os.environ.get(name, dotenv.get(name, default))

    # env: SETUP_DOCTOR_*
    cfg.default_mode = setting("SETUP_DOCTOR_MODE", cfg.default_mode) or cfg.default_mode
    cfg.output_format = setting("SETUP_DOCTOR_FORMAT", cfg.output_format) or cfg.output_format
    env_ai = setting("SETUP_DOCTOR_AI")
    if env_ai is not None:
        cfg.ai.enabled = env_ai.lower() in ("1", "true", "yes")
    ai_model = setting("SETUP_DOCTOR_AI_MODEL")
    if ai_model:
        cfg.ai.model = ai_model
    cfg.ai.api_key = setting("SETUP_DOCTOR_API_KEY")
    # CLI overrides win (chỉ ghi đè khi giá trị được cung cấp thật sự)
    if overrides:
        if overrides.get("mode"):
            cfg.default_mode = overrides["mode"]
        if overrides.get("format"):
            cfg.output_format = overrides["format"]
        if overrides.get("ai") is not None:   # None nghĩa là không truyền cờ
            cfg.ai.enabled = overrides["ai"]
    return cfg


def _resolve_dotenv_path(config_path: str | None) -> str | None:
    """Find a local .env beside config, then cwd, then tool config home."""
    candidates = []
    if config_path:
        candidates.append(os.path.join(os.path.dirname(os.path.abspath(config_path)), ".env"))
    candidates.extend((
        os.path.join(os.getcwd(), ".env"),
        os.path.join(os.path.expanduser("~"), ".setup-doctor", ".env"),
    ))
    return next((path for path in candidates if os.path.isfile(path)), None)


def _load_dotenv(path: str | None) -> dict[str, str]:
    """Read simple KEY=value entries without adding a dotenv dependency."""
    if path is None:
        return {}
    values: dict[str, str] = {}
    with open(path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, value = line.split("=", 1)
            key = key.strip()
            if key:
                values[key] = value.strip().strip('"').strip("'")
    return values


def _resolve_config_path(path: str | None, search_from) -> str | None:
    """Tìm config theo thứ tự: path truyền rõ -> search_from/setup-doctor.toml -> home."""
    if path:
        return path
    candidates = []
    if search_from is not None:
        candidates.append(os.path.join(os.fspath(search_from), "setup-doctor.toml"))
    candidates.append(os.path.join(os.getcwd(), "setup-doctor.toml"))
    candidates.append(os.path.join(os.path.expanduser("~"), ".setup-doctor", "setup-doctor.toml"))
    for cand in candidates:
        if os.path.isfile(cand):
            return cand
    return None
