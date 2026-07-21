from __future__ import annotations

from typing import List

from .model import RepoReport


def recommend(report: RepoReport) -> List[str]:
    if report.errors:
        return ["Fix audit access or repository lookup before making maintenance decisions."]

    items: List[str] = []

    failed_run = (
        report.latest_run
        and report.latest_run.status == "completed"
        and report.latest_run.conclusion not in (None, "success", "skipped")
    )
    if failed_run:
        items.append("Investigate the latest default-branch workflow failure before filing new work.")

    if report.open_prs:
        items.append("Review open pull requests before filing overlapping issues.")

    if not report.open_issues:
        items.append("Backlog is empty; run a contract/docs/CI audit and file only confirmed gaps.")

    if report.latest_run is None:
        items.append("No default-branch workflow run found; consider adding CI if this repo has executable code.")

    if not items:
        items.append("Backlog and CI are active; choose the smallest high-trust issue already filed.")

    return items

