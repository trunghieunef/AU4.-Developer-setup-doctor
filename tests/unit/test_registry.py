# tests/unit/test_registry.py
import os
import pytest
from setup_doctor.registry import detect_ecosystems, get_checkers


def make_repo(tmp_path, files):
    for rel in files:
        p = tmp_path / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text("{}", encoding="utf-8")
    return tmp_path


def test_detect_node_and_services(tmp_path):
    repo = make_repo(tmp_path, ["package.json", "docker-compose.yml", "src/main.ts"])
    assert detect_ecosystems(str(repo)) == {"node", "services"}


def test_detect_python(tmp_path):
    repo = make_repo(tmp_path, ["pyproject.toml", "src/app.py"])
    assert detect_ecosystems(str(repo)) == {"python"}


def test_detect_java_and_dotnet(tmp_path):
    repo = make_repo(tmp_path, ["pom.xml", "App.sln"])
    assert detect_ecosystems(str(repo)) == {"java", "dotnet"}


def test_detect_skips_vendor_dirs(tmp_path):
    repo = make_repo(tmp_path, ["package.json", "node_modules/pkg/index.js"])
    assert detect_ecosystems(str(repo)) == {"node"}


def test_detect_skips_test_and_backup_dirs(tmp_path):
    repo = make_repo(tmp_path, [
        "pyproject.toml",
        ".pytest-tmp/fixture/pom.xml",
        ".setup-doctor-backup/stamp/App.csproj",
    ])
    assert detect_ecosystems(str(repo)) == {"python"}


def test_get_checkers_returns_only_matching_ecosystems():
    checkers = get_checkers({"node"})
    eco = {c.ecosystem for c in checkers}
    assert eco == {"node"}

    assert get_checkers(set()) == []
