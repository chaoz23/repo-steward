from __future__ import annotations

from typing import List

from .model import Recommendation, RepoReport


def recommend(report: RepoReport) -> List[Recommendation]:
    if report.errors:
        return [
            Recommendation(
                kind="audit_error",
                title="Fix audit access before making maintenance decisions",
                confidence="high",
                reason="Repository metadata could not be read, so public maintenance decisions would be guesswork.",
                safe_next_command=f"repo-steward audit --repo {report.name}",
            )
        ]

    items: List[Recommendation] = []

    failed_run = (
        report.latest_run
        and report.latest_run.status == "completed"
        and report.latest_run.conclusion not in (None, "success", "skipped")
    )
    if failed_run:
        items.append(
            Recommendation(
                kind="public_repo_work",
                title="Investigate latest default-branch workflow failure",
                confidence="high",
                reason="A failing default-branch workflow should be understood before adding more repo work.",
                github_artifact=report.latest_run.url if report.latest_run else "",
            )
        )

    if report.open_prs:
        first = report.open_prs[0]
        items.append(
            Recommendation(
                kind="review_existing_artifact",
                title="Review open pull requests before filing overlapping issues",
                confidence="high",
                reason="Open PRs may already represent the correct tracking artifact.",
                github_artifact=first.url,
                requires_confirmation=True,
            )
        )

    if report.local_checkout and report.local_checkout.status != "clean":
        items.append(
            Recommendation(
                kind="local_hygiene",
                title="Resolve local checkout state separately from public repo work",
                confidence="high",
                reason="Local git state can be stale or accidental and should not become a public issue unless it exposes a reproducible repo policy gap.",
                safe_next_command=f"git -C {report.local_checkout.path} status --short --branch",
                local_only=True,
            )
        )

    if not report.open_issues:
        items.append(
            Recommendation(
                kind="public_repo_work",
                title="Run a contract/docs/CI audit before filing new issues",
                confidence="medium",
                reason="The backlog is empty, so new issues should come from confirmed gaps rather than vague maintenance intent.",
                safe_next_command=f"repo-steward audit --repo {report.name} --format tracker",
            )
        )

    if report.latest_run is None:
        items.append(
            Recommendation(
                kind="public_repo_work",
                title="Consider adding CI if this repo has executable code",
                confidence="medium",
                reason="No default-branch workflow run was found.",
            )
        )

    if not items:
        items.append(
            Recommendation(
                kind="public_repo_work",
                title="Choose the smallest high-trust issue already filed",
                confidence="medium",
                reason="Backlog and CI are active; existing tracked work should beat duplicate filing.",
                github_artifact=report.open_issues[0].url if report.open_issues else "",
            )
        )

    return items[:3]
