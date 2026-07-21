from __future__ import annotations

import argparse
import json
import sys
from datetime import date
from pathlib import Path
from typing import Iterable, List, Optional

from .github import audit_repos
from .issue_plan import plan_issue_filing, render_issue_plan_json, render_issue_plan_markdown
from .local import inspect_checkouts_by_repo
from .model import RepoReport
from .recommend import recommend
from .render import render_console, render_json, render_markdown, render_tracker


MUTATION_COMMANDS = {"open-pr", "verify-pr", "merge-green"}


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="repo-steward",
        description="Safety-first GitHub portfolio maintenance harness for agents.",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    audit = subparsers.add_parser("audit", help="Generate a read-only portfolio report.")
    audit.add_argument("--repo", action="append", default=[], help="Repository as owner/name.")
    audit.add_argument("--portfolio", help="Read owner/name repositories from a newline-delimited file.")
    audit.add_argument("--from-json", help="Load report input from a JSON fixture instead of gh.")
    audit.add_argument(
        "--with-local-checkouts",
        help="Directory containing local checkouts named after their repositories.",
    )
    audit.add_argument("--format", choices=["markdown", "json", "tracker", "console"], default="markdown")
    audit.add_argument("--out", help="Write report to this path instead of stdout.")

    daily = subparsers.add_parser(
        "daily",
        help="Write timestamped read-only audit, tracker, issue-plan, and summary artifacts.",
    )
    daily.add_argument("--repo", action="append", default=[], help="Repository as owner/name.")
    daily.add_argument("--portfolio", help="Read owner/name repositories from a newline-delimited file.")
    daily.add_argument("--from-json", help="Load report input from a JSON fixture instead of gh.")
    daily.add_argument(
        "--with-local-checkouts",
        help="Directory containing local checkouts named after their repositories.",
    )
    daily.add_argument("--out-dir", required=True, help="Directory for daily artifacts.")
    daily.add_argument("--date", help="Override report date prefix, in YYYY-MM-DD form.")

    file_issues = subparsers.add_parser(
        "file-issues",
        help="Plan issue filing from audit output. Only --dry-run is supported.",
    )
    file_issues.add_argument("--from-json", required=True, help="Load audit JSON produced by repo-steward.")
    file_issues.add_argument("--dry-run", action="store_true", help="Required; never mutates GitHub.")
    file_issues.add_argument("--format", choices=["markdown", "json"], default="markdown")
    file_issues.add_argument("--out", help="Write plan to this path instead of stdout.")

    for command in sorted(MUTATION_COMMANDS):
        blocked = subparsers.add_parser(command, help="Reserved for future human-gated workflows.")
        blocked.add_argument("--confirm", action="store_true", help="Reserved; no effect in v0.")

    return parser


def _load_from_json(path: str) -> List[RepoReport]:
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    reports = [RepoReport.from_dict(item) for item in data.get("repositories", [])]
    for report in reports:
        if not report.recommendations:
            report.recommendations = recommend(report)
    return reports


def _load_portfolio(path: str) -> List[str]:
    repos: List[str] = []
    for line in Path(path).read_text(encoding="utf-8").splitlines():
        clean = line.strip()
        if clean and not clean.startswith("#"):
            repos.append(clean)
    return repos


def _write(text: str, path: Optional[str]) -> None:
    if path:
        Path(path).write_text(text, encoding="utf-8")
    else:
        sys.stdout.write(text)


def _load_reports_from_args(args: argparse.Namespace) -> List[RepoReport]:
    if args.from_json:
        reports = _load_from_json(args.from_json)
    else:
        repos = list(args.repo)
        if args.portfolio:
            repos.extend(_load_portfolio(args.portfolio))
        if not repos:
            raise SystemExit("audit requires at least one --repo or --from-json")
        reports = audit_repos(repos)

    locals_by_name = inspect_checkouts_by_repo(args.with_local_checkouts)
    if locals_by_name:
        for report in reports:
            short_name = report.name.split("/")[-1]
            if short_name in locals_by_name:
                report.local_checkout = locals_by_name[short_name]
                report.recommendations = recommend(report)
    return reports


def run_audit(args: argparse.Namespace) -> int:
    reports = _load_reports_from_args(args)
    if args.format == "json":
        text = render_json(reports)
    elif args.format == "tracker":
        text = render_tracker(reports)
    elif args.format == "console":
        text = render_console(reports)
    else:
        text = render_markdown(reports)
    _write(text, args.out)
    return 1 if any(report.errors for report in reports) else 0


def run_daily(args: argparse.Namespace) -> int:
    reports = _load_reports_from_args(args)
    run_date = args.date or date.today().isoformat()
    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    audit_path = out_dir / f"{run_date}-audit.json"
    tracker_path = out_dir / f"{run_date}-tracker.md"
    issue_plan_path = out_dir / f"{run_date}-issue-plan.md"
    summary_path = out_dir / f"{run_date}-summary.md"

    issue_plan = plan_issue_filing(reports)
    audit_path.write_text(render_json(reports), encoding="utf-8")
    tracker_path.write_text(render_tracker(reports), encoding="utf-8")
    issue_plan_path.write_text(render_issue_plan_markdown(issue_plan), encoding="utf-8")
    summary_path.write_text(
        _render_daily_summary(reports, issue_plan, audit_path, tracker_path, issue_plan_path),
        encoding="utf-8",
    )
    return 1 if any(report.errors for report in reports) else 0


def run_file_issues(args: argparse.Namespace) -> int:
    if not args.dry_run:
        sys.stderr.write("file-issues only supports --dry-run; no GitHub mutation was attempted\n")
        return 2
    reports = _load_from_json(args.from_json)
    plan = plan_issue_filing(reports)
    text = render_issue_plan_json(plan) if args.format == "json" else render_issue_plan_markdown(plan)
    _write(text, args.out)
    return 0


def main(argv: Optional[Iterable[str]] = None) -> int:
    parser = build_parser()
    args = parser.parse_args(list(argv) if argv is not None else None)
    if args.command == "audit":
        return run_audit(args)
    if args.command == "daily":
        return run_daily(args)
    if args.command == "file-issues":
        return run_file_issues(args)
    if args.command in MUTATION_COMMANDS:
        parser.error(f"{args.command} is intentionally unavailable in v0; run audit first")
    parser.error("unknown command")
    return 2


def _render_daily_summary(
    reports: Iterable[RepoReport],
    issue_plan: object,
    audit_path: Path,
    tracker_path: Path,
    issue_plan_path: Path,
) -> str:
    repo_list = list(reports)
    issue_plan_data = issue_plan.to_dict()
    error_count = sum(1 for report in repo_list if report.errors)
    open_pr_count = sum(len(report.open_prs) for report in repo_list)
    open_issue_count = sum(len(report.open_issues) for report in repo_list)
    proposed_count = len(issue_plan_data["proposed_issues"])
    suppressed_count = len(issue_plan_data["suppressed"])
    return (
        "# Daily repo-steward Summary\n\n"
        f"- Repositories audited: {len(repo_list)}\n"
        f"- Repositories with audit errors: {error_count}\n"
        f"- Open pull requests observed: {open_pr_count}\n"
        f"- Open issues observed: {open_issue_count}\n"
        f"- Dry-run issue proposals: {proposed_count}\n"
        f"- Suppressed issue proposals: {suppressed_count}\n\n"
        "Artifacts:\n"
        f"- Audit JSON: `{audit_path}`\n"
        f"- Tracker: `{tracker_path}`\n"
        f"- Dry-run issue plan: `{issue_plan_path}`\n\n"
        "No GitHub mutations were attempted.\n"
    )
