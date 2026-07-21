from __future__ import annotations

import json
import subprocess
from typing import Any, List

from .model import Issue, PullRequest, RepoReport, WorkflowRun
from .recommend import recommend


class GhError(RuntimeError):
    pass


def _run_gh(args: List[str]) -> Any:
    process = subprocess.run(
        ["gh", *args],
        check=False,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    if process.returncode != 0:
        message = process.stderr.strip() or process.stdout.strip() or "gh command failed"
        raise GhError(message)
    text = process.stdout.strip()
    if not text:
        return None
    return json.loads(text)


def audit_repo(name: str) -> RepoReport:
    try:
        repo = _run_gh(
            [
                "repo",
                "view",
                name,
                "--json",
                "nameWithOwner,url,description,visibility,defaultBranchRef",
            ]
        )
        issues = _run_gh(
            [
                "issue",
                "list",
                "--repo",
                name,
                "--state",
                "open",
                "--limit",
                "50",
                "--json",
                "number,title,url",
            ]
        ) or []
        prs = _run_gh(
            [
                "pr",
                "list",
                "--repo",
                name,
                "--state",
                "open",
                "--limit",
                "50",
                "--json",
                "number,title,url,isDraft",
            ]
        ) or []
        default_branch = (repo.get("defaultBranchRef") or {}).get("name") or "main"
        runs = _run_gh(
            [
                "run",
                "list",
                "--repo",
                name,
                "--branch",
                default_branch,
                "--limit",
                "1",
                "--json",
                "workflowName,status,conclusion,url",
            ]
        ) or []

        report = RepoReport(
            name=str(repo["nameWithOwner"]),
            url=str(repo.get("url") or ""),
            description=str(repo.get("description") or ""),
            visibility=str(repo.get("visibility") or ""),
            default_branch=default_branch,
            open_issues=[Issue.from_gh(item) for item in issues],
            open_prs=[PullRequest.from_gh(item) for item in prs],
            latest_run=WorkflowRun.from_gh(runs[0]) if runs else None,
        )
    except (GhError, json.JSONDecodeError, KeyError) as exc:
        report = RepoReport(name=name, url="", errors=[str(exc)])

    report.recommendations = recommend(report)
    return report


def audit_repos(names: List[str]) -> List[RepoReport]:
    return [audit_repo(name) for name in names]

