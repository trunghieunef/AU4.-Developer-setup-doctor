# src/setup_doctor/utils/versions.py
from __future__ import annotations
import re

_VERSION_RE = re.compile(r"(\d+(?:\.\d+){0,3})")


def _compare(left: tuple[int, ...], right: tuple[int, ...]) -> int:
    width = max(len(left), len(right))
    left = left + (0,) * (width - len(left))
    right = right + (0,) * (width - len(right))
    return (left > right) - (left < right)


def parse_version(s: str) -> tuple[int, ...]:
    """Extract the first dotted-numeric version from a string."""
    match = _VERSION_RE.search(s or "")
    if not match:
        return ()
    return tuple(int(p) for p in match.group(1).split("."))


def satisfies(installed: str, constraint: str) -> bool | None:
    """Check an installed version string against a constraint.

    Hỗ trợ: ``>=X``, ``>X``, ``<X``, ``<=X``, ``^X`` (major-pinned),
    ``~X.Y.Z`` (patch-pinned), khoảng ``a b``, và ``a || b`` (OR).

    Trả về:
    - ``True``/``False`` nếu constraint hợp lệ.
    - ``None`` nếu **không xác định được** (constraint không hỗ trợ, hoặc
      version không parse được) — caller KHÔNG được coi là fail; phải báo
      ``skip``/``warning`` để tránh fail sai.
    """
    iv = parse_version(installed)
    if not iv:
        return None
    c = constraint.strip()
    # Chuẩn hóa: bỏ khoảng trắng sau operator (vd ">= 18" -> ">=18", "~ 20" -> "~20").
    # Đúng semver convention; tránh nhầm ">= 18" thành khoảng version 2 phần.
    c = re.sub(r"(>=|<=|==|!=|>|<|\^|~)\s+", r"\1", c)
    c = c.strip()
    if not c or c.lower() in ("*", "latest", "x", "X"):
        return None  # không ràng buộc khả thi để so sánh -> chưa xác định
    if "lts" in c.lower() or "/" in c:
        return None  # dạng alias (lts/*, node/*...) -> chưa xác định
    # OR
    if "||" in c:
        results = [satisfies(installed, part.strip()) for part in c.split("||")]
        # nếu có vế None (unsupported) -> không thể kết luận chắc chắn -> None
        if any(r is None for r in results):
            return None
        return any(results)
    # khoảng cách (nhiều ràng buộc, cách nhau khoảng trắng)
    parts = c.split()
    if len(parts) > 1:
        results = [satisfies(installed, p) for p in parts]
        if any(r is None for r in results):
            return None
        return all(results)
    single = parts[0]
    # khử dấu v ở đầu
    single = single.lstrip("vV")
    if single.startswith(">="):
        cv = parse_version(single[2:])
        return None if not cv else _compare(iv, cv) >= 0
    if single.startswith(">"):
        cv = parse_version(single[1:])
        return None if not cv else _compare(iv, cv) > 0
    if single.startswith("<="):
        cv = parse_version(single[2:])
        return None if not cv else _compare(iv, cv) <= 0
    if single.startswith("<"):
        cv = parse_version(single[1:])
        return None if not cv else _compare(iv, cv) < 0
    if single.startswith("^"):
        cv = parse_version(single[1:])
        if not cv:
            return None
        return iv[0] == cv[0] and _compare(iv, cv) >= 0
    if single.startswith("~"):
        cv = parse_version(single[1:])
        if not cv:
            return None
        # ~X.Y.Z -> >= X.Y.Z, < X.(Y+1).0
        if len(cv) >= 2:
            return _compare(iv, cv) >= 0 and _compare(iv, (cv[0], cv[1] + 1, 0)) < 0
        return _compare(iv, cv) >= 0
    cv = parse_version(single)
    if not cv:
        return None  # không parse được constraint (vd "~dev") -> chưa xác định
    return _compare(iv, cv) >= 0  # plain major = minimum major
