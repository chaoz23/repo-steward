from __future__ import annotations

import json
from typing import Iterable, List

from .model import RepoReport


def render_json(reports: Iterable[RepoReport]) -> str:
    return json.dumps({"repositories": [report.to_dict() for report in reports]}, indent=2) + "\n"


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
        next_action = report.recommendations[0] if report.recommendations else ""
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
            lines.append(f"- {item}")
        lines.append("")
    return "\n".join(lines).rstrip() + "\n"

