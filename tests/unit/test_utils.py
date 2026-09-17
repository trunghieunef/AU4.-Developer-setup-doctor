# tests/unit/test_utils.py
from setup_doctor.utils.commands import run_command, CommandResult
from setup_doctor.utils.versions import satisfies, parse_version

def test_run_command_captures_output():
    res = run_command(["python", "--version"], timeout=10)
    assert res.ok is True
    assert "Python" in res.stdout

def test_run_command_missing_binary():
    res = run_command(["definitely-not-a-command-xyz"], timeout=10)
    assert res.returncode == -1
    assert "not found" in res.stderr

def test_run_command_timeout():
    res = run_command(["python", "-c", "import time; time.sleep(5)"], timeout=1)
    assert res.returncode == -1
    assert "timed out" in res.stderr

def test_satisfies_semver():
    assert satisfies("v22.3.0", ">=20.0.0")
    assert not satisfies("18.16.0", ">=20.0.0")
    assert satisfies("21.0.2", "21")
    # ^20.0.0 = >=20.0.0, <21.0.0 (caret giữ major)
    assert satisfies("20.5.0", "^20.0.0")
    assert not satisfies("21.0.0", "^20.0.0")
    assert not satisfies("22.1.0", "^20.0.0")
    assert not satisfies("19.0.0", "^20.0.0")
    assert not satisfies("20.5.0", "~20.4.0")   # ~20.4.0 = >=20.4.0, <20.5.0 -> 20.5.0 KHÔNG thỏa
    assert satisfies("20.4.9", "~20.4.0")
    assert not satisfies("20.6.0", "~20.4.0")
    assert satisfies("18.0.0", "<20.0.0")
    assert not satisfies("20.0.0", "<20.0.0")
    assert satisfies("20.0.0", "<=20.0.0")
    assert satisfies("19.0.0", ">18.0.0")
    assert satisfies("22.1.0", ">=20 <23")          # khoảng: 20 <= v < 23
    assert not satisfies("23.1.0", ">=20 <23")
    assert satisfies("20.0.0", ">=18.0.0 || >=22.0.0")
    assert satisfies("19.0.0", ">=18.0.0 || >=22.0.0")  # 19 >= 18 -> thỏa vế trái

def test_satisfies_unsupported_constraint_returns_none():
    # constraint không hỗ trợ (vd "lts/*") -> trả None, KHÔNG fail sai
    assert satisfies("20.0.0", "lts/*") is None
    assert satisfies("20.0.0", "~dev") is None
    assert satisfies("", ">=20") is None          # không parse được version -> None
    assert satisfies("20.0.0", ">=foo") is None
    assert satisfies("20.0.0", "<foo") is None


def test_satisfies_operator_with_space_after():
    # Bug thật từ Express (package.json: "node": ">= 18") — có khoảng trắng sau operator
    assert satisfies("v24.14.1", ">= 18")
    assert satisfies("20.5.0", "~ 20.4.0") is False  # ~20.4.x, 20.5 không thỏa
    assert satisfies("20.4.9", "~ 20.4.0")
    assert satisfies("18.1.0", "< 20.0.0")


def test_satisfies_treats_missing_version_parts_as_zero():
    assert satisfies("3.11", ">=3.11.0")
    assert satisfies("3.11", "<=3.11.0")
    assert satisfies("3.11", "~3.11.0")
    assert not satisfies("3.11", ">3.11.0")


def test_parse_version_extracts_numbers():
    assert parse_version("Node.js v20.11.1") == (20, 11, 1)
    assert parse_version("") == ()

def test_parse_version_prerelease_ignored():
    assert parse_version("20.0.0-beta.1") == (20, 0, 0)
