from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Iterable, List, Optional

from .github import audit_repos
from .model import RepoReport
from .recommend import recommend
from .render import render_json, render_markdown


MUTATION_COMMANDS = {"file-issues", "open-pr", "verify-pr", "merge-green"}


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="repo-steward",
        description="Safety-first GitHub portfolio maintenance harness for agents.",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    audit = subparsers.add_parser("audit", help="Generate a read-only portfolio report.")
    audit.add_argument("--repo", action="append", default=[], help="Repository as owner/name.")
    audit.add_argument("--from-json", help="Load report input from a JSON fixture instead of gh.")
    audit.add_argument("--format", choices=["markdown", "json"], default="markdown")
    audit.add_argument("--out", help="Write report to this path instead of stdout.")

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


def _write(text: str, path: Optional[str]) -> None:
    if path:
        Path(path).write_text(text, encoding="utf-8")
    else:
        sys.stdout.write(text)


def run_audit(args: argparse.Namespace) -> int:
    if args.from_json:
        reports = _load_from_json(args.from_json)
    else:
        if not args.repo:
            raise SystemExit("audit requires at least one --repo or --from-json")
        reports = audit_repos(args.repo)

    text = render_json(reports) if args.format == "json" else render_markdown(reports)
    _write(text, args.out)
    return 1 if any(report.errors for report in reports) else 0


def main(argv: Optional[Iterable[str]] = None) -> int:
    parser = build_parser()
    args = parser.parse_args(list(argv) if argv is not None else None)
    if args.command == "audit":
        return run_audit(args)
    if args.command in MUTATION_COMMANDS:
        parser.error(f"{args.command} is intentionally unavailable in v0; run audit first")
    parser.error("unknown command")
    return 2

