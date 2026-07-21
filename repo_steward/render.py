from __future__ import annotations

import json
from typing import Iterable, List

from .model import RepoReport, SCHEMA_VERSION


def render_json(reports: Iterable[RepoReport]) -> str:
    return json.dumps(
        {"schema_version": SCHEMA_VERSION, "repositories": [report.to_dict() for report in reports]},
        indent=2,
    ) + "\n"


def render_markdown(reports: Iterable[RepoReport]) -> str:
    repo_list = list(reports)
    lines: List[str] = [
        "# GitHub Portfolio Stewardship Report",
        "",
        "| Repository | Open Issues | Open PRs | Latest Default-Branch CI | Next Action |",
        "| --- | ---: | ---: | --- | --- |",
    ]
    for report in repo_list:
        ci = "none"
        if report.latest_run:
            ci = f"{report.latest_run.workflow_name}: {report.latest_run.status}"
            if report.latest_run.conclusion:
                ci += f" / {report.latest_run.conclusion}"
        if report.errors:
            ci = "audit error"
        next_action = report.recommendations[0].title if report.recommendations else ""
        name = f"[{report.name}]({report.url})" if report.url else report.name
        lines.append(
            f"| {name} | {len(report.open_issues)} | {len(report.open_prs)} | {ci} | {next_action} |"
        )

    lines.append("")
    for report in repo_list:
        lines.append(f"## {report.name}")
        lines.append("")
        if report.errors:
            lines.append("Audit errors:")
            for error in report.errors:
                lines.append(f"- {error}")
            lines.append("")
        if report.open_prs:
            lines.append("Open PRs:")
            for pr in report.open_prs:
                prefix = "draft " if pr.is_draft else ""
                lines.append(f"- {prefix}#{pr.number}: [{pr.title}]({pr.url})")
            lines.append("")
        if report.open_issues:
            lines.append("Open issues:")
            for issue in report.open_issues[:10]:
                lines.append(f"- #{issue.number}: [{issue.title}]({issue.url})")
            if len(report.open_issues) > 10:
                lines.append(f"- ...and {len(report.open_issues) - 10} more")
            lines.append("")
        lines.append("Recommendations:")
        for item in report.recommendations:
            label = "local" if item.local_only else item.kind
            lines.append(f"- [{label}] {item.title}: {item.reason}")
        lines.append("")
    return "\n".join(lines).rstrip() + "\n"


def render_console(reports: Iterable[RepoReport]) -> str:
    lines = ["REPOSITORY                         CI                  PRS  ISSUES  NEXT"]
    for report in reports:
        ci = "none"
        if report.latest_run:
            ci = report.latest_run.conclusion or report.latest_run.status or "unknown"
        if report.errors:
            ci = "error"
        next_action = report.recommendations[0].title if report.recommendations else ""
        lines.append(
            f"{_trim(report.name, 34):34} {_trim(ci, 19):19} "
            f"{len(report.open_prs):>3}  {len(report.open_issues):>6}  {_trim(next_action, 60)}"
        )
    return "\n".join(lines).rstrip() + "\n"


def render_tracker(reports: Iterable[RepoReport]) -> str:
    lines = [
        "# GitHub Work Tracker",
        "",
        "| Repository | Local checkout | Active work | Pull request | CI | Pickup point |",
        "| --- | --- | --- | --- | --- | --- |",
    ]
    for report in reports:
        local = "unknown"
        if report.local_checkout:
            local = f"`{report.local_checkout.path}`"
        branch = report.default_branch
        if report.local_checkout and report.local_checkout.branch:
            branch = report.local_checkout.branch
        prs = "None"
        if report.open_prs:
            prs = "; ".join(
                f"[#{pr.number}]({pr.url}){' draft' if pr.is_draft else ''}" for pr in report.open_prs[:3]
            )
        issues = ""
        if report.open_issues:
            issues = f"; {len(report.open_issues)} open issue(s)"
        ci = "No default-branch run"
        if report.latest_run:
            ci = f"{report.latest_run.workflow_name}: {report.latest_run.status}"
            if report.latest_run.conclusion:
                ci += f" / {report.latest_run.conclusion}"
        if report.errors:
            ci = "Audit error"
        pickup = report.recommendations[0].title if report.recommendations else ""
        if report.local_checkout and report.local_checkout.notes:
            pickup += f" Local: {'; '.join(report.local_checkout.notes)}."
        lines.append(
            f"| `{report.name}` | {local} | `{branch}` | {prs}{issues} | {ci} | {pickup} |"
        )
    return "\n".join(lines).rstrip() + "\n"


def _trim(value: str, width: int) -> str:
    if len(value) <= width:
        return value
    return value[: max(0, width - 1)] + "…"
