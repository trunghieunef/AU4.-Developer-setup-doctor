# tests/unit/test_config.py
import os
import textwrap
import pytest
from setup_doctor.config import load_config


def test_defaults(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    cfg = load_config()
    assert cfg.default_mode == "dep"
    assert cfg.output_format == "text"
    assert cfg.ai.enabled is False
    assert cfg.ai.provider == "openai"
    assert cfg.ai.max_requests == 10


def test_config_file(tmp_path):
    cfg_file = tmp_path / "setup-doctor.toml"
    cfg_file.write_text(textwrap.dedent("""
        [mode]
        default = "flat"
        [ai]
        enabled = true
        provider = "anthropic"
        max_requests = 3
        [output]
        format = "json"
    """), encoding="utf-8")
    cfg = load_config(str(cfg_file))
    assert cfg.default_mode == "flat"
    assert cfg.ai.enabled is True
    assert cfg.ai.provider == "anthropic"
    assert cfg.ai.max_requests == 3
    assert cfg.output_format == "json"


def test_cli_overrides_file_and_env(tmp_path, monkeypatch):
    cfg_file = tmp_path / "setup-doctor.toml"
    cfg_file.write_text('[mode]\ndefault = "flat"\n[ai]\nenabled = true\n', encoding="utf-8")
    monkeypatch.delenv("SETUP_DOCTOR_MODE", raising=False)
    cfg = load_config(str(cfg_file), overrides={"mode": "dep"})
    assert cfg.default_mode == "dep"       # CLI wins
    assert cfg.ai.enabled is True          # không bị CLI ghi đè vì overrides không có "ai"


def test_ai_flag_tristate(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    monkeypatch.delenv("SETUP_DOCTOR_AI", raising=False)
    cfg = load_config(overrides={"ai": True})
    assert cfg.ai.enabled is True
    cfg2 = load_config(overrides={"ai": None})
    assert cfg2.ai.enabled is False        # None = không truyền -> không ghi đè


def test_auto_discover_config_in_repo(tmp_path, monkeypatch):
    (tmp_path / "setup-doctor.toml").write_text('[mode]\ndefault = "flat"\n', encoding="utf-8")
    cfg = load_config(search_from=tmp_path)
    assert cfg.default_mode == "flat"


def test_dotenv_loads_ai_settings_without_overriding_shell(tmp_path, monkeypatch):
    cfg_file = tmp_path / "setup-doctor.toml"
    cfg_file.write_text("", encoding="utf-8")
    (tmp_path / ".env").write_text(
        'SETUP_DOCTOR_API_KEY="from-file"\nSETUP_DOCTOR_AI_MODEL=from-dotenv\n',
        encoding="utf-8",
    )
    monkeypatch.delenv("SETUP_DOCTOR_API_KEY", raising=False)
    monkeypatch.setenv("SETUP_DOCTOR_AI_MODEL", "from-shell")
    cfg = load_config(str(cfg_file))
    assert cfg.ai.api_key == "from-file"
    assert cfg.ai.model == "from-shell"
