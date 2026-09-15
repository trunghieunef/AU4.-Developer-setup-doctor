# src/setup_doctor/study/runner.py
from __future__ import annotations
import csv
import json
import os
from pathlib import Path
from ..engine import diagnose
from ..registry import detect_ecosystems, get_checkers
from ..context import CheckContext
from ..utils.osdetect import detect_os
from .metrics import compute_metrics
from .ground_truth import load_ground_truth


def _registry_relevant(repo_path: str) -> bool:
    """Giống runner.run_check: registry only khi repo có .npmrc/pip.conf/.pypirc hoặc .git config."""
    for name in (".npmrc", "pip.conf", "pip.ini", ".pypirc"):
        if os.path.isfile(os.path.join(repo_path, name)):
            return True
    return os.path.isfile(os.path.join(repo_path, ".git", "config"))


def _ground_truth_map(path: str) -> dict[str, dict]:
    result: dict[str, dict] = {}
    if not path:
        return result
    p = Path(path)
    if p.is_dir():
        for f in sorted(p.glob("*.json")):
            data = load_ground_truth(str(f))
            result[data["repo"]] = data
    else:
        data = load_ground_truth(str(Path(path)))
        result[data["repo"]] = data
    return result


def run_study(repos_file: str, ground_truth_path: str | None, output_dir: str) -> str:
    repos = [line.strip() for line in open(repos_file, encoding="utf-8") if line.strip()]
    gt = _ground_truth_map(ground_truth_path) if ground_truth_path else {}
    os.makedirs(output_dir, exist_ok=True)
    rows: list[dict] = []
    os_name = detect_os()
    for repo in repos:
        gt_entry = gt.get(repo, {})
        ecosystems = detect_ecosystems(repo)
        # Registry chỉ chạy khi repo thật sự cần (giống runner.check) — tránh fail giả.
        target = set(ecosystems)
        if _registry_relevant(repo):
            target.add("registry")
        checkers = get_checkers(target) if target else []
        checks = []
        if checkers:
            ctx = CheckContext(repo_path=repo, os=os_name)
            for checker in checkers:
                checks.extend(checker.run(ctx))
        for mode in ("flat", "dep"):
            report = diagnose(checks, mode, repo, os_name)
            metrics = compute_metrics(report, gt_entry)
            rows.append({"repo": repo, "mode": mode, **metrics})
    # write outputs
    csv_path = os.path.join(output_dir, "study_results.csv")
    with open(csv_path, "w", newline="", encoding="utf-8") as f:
        fieldnames = list(rows[0].keys()) if rows else ["repo", "mode"]
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)
    json_path = os.path.join(output_dir, "study_results.json")
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(rows, f, indent=2, ensure_ascii=False)
    return csv_path