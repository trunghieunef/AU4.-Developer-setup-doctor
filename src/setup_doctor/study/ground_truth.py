# src/setup_doctor/study/ground_truth.py
from __future__ import annotations
import json

CATALOG_CHECK_IDS = {
    "node.runtime.present", "node.sdk.version", "node.pkgmgr.present",
    "node.lockfile.exists", "node.deps.installed", "node.build.ready",
    "python.runtime.present", "python.version", "python.env.present",
    "python.deps.installed", "python.build.ready",
    "java.runtime.present", "java.version", "java.maven.gradle.present",
    "java.deps.cached", "java.build.ready",
    "dotnet.runtime.present", "dotnet.sdk.version", "dotnet.restore.ready",
    "dotnet.build.ready", "services.container.present", "services.compose.up",
    "services.db.port", "services.redis", "services.envfile",
    "registry.git.user", "registry.git.ssh", "registry.npm", "registry.pypi",
}


def validate_ground_truth(data: dict, catalog_ids: set[str]) -> list[str]:
    """Kiểm tra ground truth: mọi ID trong expected_failures/passes/root_causes
    phải thuộc catalog check. Trả về danh sách lỗi (rỗng = hợp lệ).

    (điểm #7 review) — ID ngoài catalog bị từ chối để universe luôn có ý nghĩa.
    """
    errors: list[str] = []
    for field in ("expected_failures", "expected_passes", "expected_root_causes"):
        for check_id in data.get(field, []) or []:
            if check_id not in catalog_ids:
                errors.append(f"{field}: unknown check_id '{check_id}' (not in catalog)")
    return errors


def load_ground_truth(path: str) -> dict:
    """Đọc 1 file ground truth JSON và validate cấu trúc cơ bản."""
    with open(path, encoding="utf-8") as f:
        data = json.load(f)
    for key in ("repo", "expected_failures"):
        if key not in data:
            raise ValueError(f"ground truth {path} thiếu field '{key}'")
    overlap = set(data.get("expected_failures", [])) & set(data.get("expected_passes", []))
    if overlap:
        raise ValueError(f"ground truth {path} có ID vừa fail vừa pass: {sorted(overlap)}")
    errors = validate_ground_truth(data, CATALOG_CHECK_IDS)
    if errors:
        raise ValueError("invalid ground truth: " + "; ".join(errors))
    return data