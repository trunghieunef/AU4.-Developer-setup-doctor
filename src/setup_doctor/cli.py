# src/setup_doctor/cli.py
from __future__ import annotations
import argparse
import json
import os
import sys
from . import __version__
from .config import load_config
from .output import render_text, render_json
from .runner import run_check, NoEcosystemError, RepoPathError
from .fixer import Fixer
from .study.runner import run_study


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="setup-doctor")
    parser.add_argument("--version", action="version", version=f"setup-doctor {__version__}")
    sub = parser.add_subparsers(dest="command", required=True)

    check_p = sub.add_parser("check", help="diagnose one repository")
    check_p.add_argument("repo_path")
    check_p.add_argument("--mode", choices=["flat", "dep"], help="default from config")
    check_p.add_argument("--format", choices=["text", "json"], help="default from config")
    check_p.add_argument("--output", help="write JSON output to file (json only)")
    check_p.add_argument("--fix", action="store_true", help="apply safe remediations with backup")
    # --ai ba trạng thái: None (không truyền) / True / --no-ai (False) — để config ai.enabled giữ nguyên khi không truyền.
    check_p.add_argument("--ai", dest="ai", action="store_true", default=None, help="enhance remediation/explanation with LLM")
    check_p.add_argument("--no-ai", dest="ai", action="store_false", help="disable AI even if config enables it")
    check_p.add_argument("--config", help="path to setup-doctor.toml")
    check_p.add_argument("--verbose", action="store_true")

    study_p = sub.add_parser("study", help="run repeatable flat-vs-dep research")
    study_p.add_argument("repos_file")
    study_p.add_argument("--ground-truth", help="JSON file or dir of ground-truth files")
    study_p.add_argument("--output-dir", default="research/output")
    return parser


def main(argv: list[str] | None = None) -> int:
    # Windows console (cp1252) không thể encode ký tự như '→' (U+2192) trong chain
    # -> reconfigure để in an toàn, không crash khi output text ra terminal.
    try:
        sys.stdout.reconfigure(errors="replace")
        sys.stderr.reconfigure(errors="replace")
    except (AttributeError, ValueError):
        pass  # không phải stream console hoặc Python cũ hơn 3.7

    parser = _build_parser()
    args = parser.parse_args(argv)
    try:
        if args.command == "check":
            return _cmd_check(args)
        if args.command == "study":
            if not os.path.isfile(args.repos_file):
                print(f"setup-doctor: repos file not found: {args.repos_file}", file=sys.stderr)
                return 2
            run_study(args.repos_file, args.ground_truth, args.output_dir)
            return 0
    except NoEcosystemError as exc:
        # Repo không hỗ trợ: exit 0, output đúng format đã chọn (kể cả JSON).
        _emit_no_ecosystem(args, exc.repo_path)
        return 0
    except RepoPathError as exc:
        print(f"setup-doctor: invalid repo path: {exc}", file=sys.stderr)
        return 2
    except KeyboardInterrupt:
        return 130
    except Exception as exc:  # internal tool error -> exit 2
        print(f"setup-doctor: internal error: {exc}", file=sys.stderr)
        if getattr(args, "verbose", False):
            import traceback
            traceback.print_exc()
        return 2
    return 2


def _emit_no_ecosystem(args, repo_path: str) -> None:
    """No-ecosystem: vẫn tôn trọng --format json và xuất đúng schema Report (kể cả JSON)."""
    fmt = getattr(args, "format", None)
    if fmt == "json":
        payload = json.dumps({
            "schema_version": "1.0",
            "repo_path": repo_path,
            "summary": {"total": 0, "pass": 0, "fail": 0, "skip": 0, "warnings": 0},
            "checks": [],
            "message": "no supported ecosystem detected",
            "exit_code": 0,
        }, indent=2, ensure_ascii=False)
        print(payload)
    else:
        print(f"no supported ecosystem detected for {repo_path}")


def _cmd_check(args) -> int:
    config = load_config(path=args.config, search_from=args.repo_path, overrides={
        "mode": args.mode,
        "format": args.format,
        "ai": args.ai,
    })
    mode = args.mode or config.default_mode
    report = run_check(args.repo_path, mode, config, ai_enabled=bool(config.ai.enabled))
    if args.fix:
        fix = Fixer(args.repo_path).apply(report)
        if args.verbose:
            for e in fix.entries:
                print(f"fix: {e.status} -> {e.command} {e.detail}")
        # AC-3 / spec data flow 3.3: sau khi fix phải chạy lại checks để lấy trạng thái cuối
        # (exit code phản ánh kết quả SAU fix, không phải trước fix).
        report = run_check(args.repo_path, mode, config, ai_enabled=bool(config.ai.enabled))
    use_json = args.format == "json" or (args.format is None and config.output_format == "json")
    if use_json:
        payload = render_json(report)
        if args.output:
            with open(args.output, "w", encoding="utf-8") as f:
                f.write(payload)
        else:
            print(payload)
    else:
        print(render_text(report))
    return report.exit_code


if __name__ == "__main__":
    sys.exit(main())