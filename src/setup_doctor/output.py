# src/setup_doctor/output.py
from __future__ import annotations
import json
from pathlib import Path
from typing import Callable
from rich import box
from rich.console import Console, Group
from rich.panel import Panel
from rich.table import Table
from rich.text import Text
from .models import Report, CheckStatus


console = Console(highlight=False)
error_console = Console(stderr=True, highlight=False)


def _status_label(check) -> tuple[str, str]:
    if check.status == CheckStatus.PASS:
        return "PASS", "green"
    if check.status == CheckStatus.SKIP:
        return "SKIP", "dim"
    return "WARN", "yellow" if check.severity.value == "warning" else "red"


def _summary(report: Report) -> str:
    summary = report.summary
    return (
        f"[green]{summary.get('pass', 0)} passed[/]  "
        f"[red]{summary.get('fail', 0)} failed[/]  "
        f"[dim]{summary.get('skip', 0)} skipped[/]"
    )


def print_report(report: Report, target: Console | None = None) -> None:
    """Render the human-facing report; JSON rendering remains separate for CI."""
    target = target or console
    title = "SETUP DOCTOR"
    subtitle = "Ready to run" if report.exit_code == 0 else "Setup needs attention"
    target.print()
    target.print(Panel(
        Group(
            Text(subtitle, style="bold green" if report.exit_code == 0 else "bold yellow"),
            Text(f"{report.repo_path}  |  {report.os}  |  {report.mode} diagnosis", style="dim"),
            Text.from_markup(_summary(report)),
        ),
        title=f"[bold cyan]{title}[/]",
        border_style="cyan",
        box=box.ROUNDED,
        padding=(1, 2),
    ))

    checks = Table(box=box.SIMPLE_HEAVY, header_style="bold cyan", expand=True)
    checks.add_column("Status", width=8)
    checks.add_column("Check", style="bold", min_width=24)
    checks.add_column("Evidence")
    for check in report.checks:
        label, style = _status_label(check)
        checks.add_row(f"[{style}]{label}[/]", check.check_id, check.evidence or "—")
    target.print(checks)

    failed = [check for check in report.checks if check.status == CheckStatus.FAIL]
    if failed:
        fixes: list[Text] = []
        for check in failed:
            fixes.append(Text(check.name, style="bold"))
            for index, step in enumerate(check.remediation, 1):
                command = f"  $ {step.command}" if step.command else ""
                fixes.append(Text(f"  {index}. {step.step}{command}", style="white"))
        target.print(Panel(
            Group(*fixes), title="[bold yellow]HOW TO FIX[/]", border_style="yellow", box=box.ROUNDED,
        ))

    if report.diagnosis and report.diagnosis.root_causes:
        causes = [
            Text(f"{root.message}\n  {root.chain.replace(' → ', ' -> ')}", style="white")
            for root in report.diagnosis.root_causes
        ]
        target.print(Panel(
            Group(*causes), title="[bold magenta]ROOT CAUSES[/]", border_style="magenta", box=box.ROUNDED,
        ))

    code_style = "green" if report.exit_code == 0 else "red"
    target.print(f"[dim]Exit code:[/] [{code_style}]{report.exit_code}[/]")


def print_fix_report(fix_report, target: Console | None = None) -> None:
    target = target or console
    rows = Table(box=box.SIMPLE_HEAVY, header_style="bold cyan")
    rows.add_column("Status", width=12)
    rows.add_column("Operation")
    rows.add_column("Command / detail")
    for entry in fix_report.entries:
        style = {"applied": "green", "failed": "red", "rolled_back": "yellow"}.get(entry.status, "dim")
        rows.add_row(f"[{style}]{entry.status.upper()}[/]", entry.operation or "—", entry.command or entry.detail or "—")
    target.print(Panel(
        rows, title="[bold cyan]SAFE FIXES[/]", border_style="cyan", box=box.ROUNDED,
        subtitle=Path(fix_report.backup_dir).as_posix(),
    ))


def print_study_complete(csv_path: str, target: Console | None = None) -> None:
    target = target or console
    csv = Path(csv_path)
    target.print(Panel(
        f"[green]Flat vs dep study completed.[/]\nCSV: {csv}\nJSON: {csv.with_suffix('.json')}",
        title="[bold cyan]STUDY COMPLETE[/]", border_style="cyan", box=box.ROUNDED,
    ))


def print_notice(message: str, target: Console | None = None) -> None:
    (target or console).print(Panel(message, title="[bold cyan]SETUP DOCTOR[/]", border_style="cyan", box=box.ROUNDED))


def print_error(message: str) -> None:
    error_console.print(Panel(message, title="[bold red]SETUP DOCTOR ERROR[/]", border_style="red", box=box.ROUNDED))


def run_with_status(message: str, action: Callable[[], object], target: Console | None = None):
    """Show a spinner only for the human terminal path."""
    with (target or console).status(message, spinner="dots"):
        return action()


def render_text(report: Report) -> str:
    lines = [f"setup-doctor report (mode: {report.mode})",
             f"repo: {report.repo_path} | os: {report.os}",
             f"summary: {report.summary}"]
    marks = {
        CheckStatus.PASS: "[PASS]", CheckStatus.FAIL: "[FAIL]", CheckStatus.SKIP: "[SKIP]",
    }
    for c in report.checks:
        lines.append(f"{marks[c.status]} {c.check_id}: {c.evidence}")
        if c.status == CheckStatus.FAIL:
            for i, r in enumerate(c.remediation, 1):
                lines.append(f"    fix {i}: {r.step} -> {r.command}")
    if report.diagnosis and report.diagnosis.root_causes:
        lines.append("root causes:")
        for rc in report.diagnosis.root_causes:
            # ASCII-safe cho console Windows (cp1252 không hiển thị '→')
            chain = rc.chain.replace(" → ", " -> ")
            lines.append(f"  - {rc.cause_check_id}: {rc.message} (chain: {chain})")
    lines.append(f"exit_code: {report.exit_code}")
    return "\n".join(lines)


def render_json(report: Report) -> str:
    return json.dumps(report.to_dict(), indent=2, ensure_ascii=False)
