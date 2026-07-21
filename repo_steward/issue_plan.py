from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from typing import Dict, Iterable, List

from .model import Recommendation, RepoReport


ISSUE_PLAN_SCHEMA_VERSION = "1.0"


@dataclass
class ProposedIssue:
    repo: str
    title: str
    body: str
    reason: str
    confidence: str
    source_recommendation_kind: str
    requires_confirmation: bool = True

    def to_dict(self) -> Dict[str, object]:
        return {
            "repo": self.repo,
            "title": self.title,
            "body": self.body,
            "reason": self.reason,
            "confidence": self.confidence,
            "source_recommendation_kind": self.source_recommendation_kind,
            "requires_confirmation": self.requires_confirmation,
        }


@dataclass
class SuppressedIssue:
    repo: str
    title: str
    reason: str
    existing_artifact: str = ""
    local_only: bool = False

    def to_dict(self) -> Dict[str, object]:
        return {
            "repo": self.repo,
            "title": self.title,
            "reason": self.reason,
            "existing_artifact": self.existing_artifact,
            "local_only": self.local_only,
        }


@dataclass
class IssueFilingPlan:
    dry_run: bool = True
    proposed_issues: List[ProposedIssue] = field(default_factory=list)
    suppressed: List[SuppressedIssue] = field(default_factory=list)

    def to_dict(self) -> Dict[str, object]:
        return {
            "schema_version": ISSUE_PLAN_SCHEMA_VERSION,
            "dry_run": self.dry_run,
            "proposed_issues": [issue.to_dict() for issue in self.proposed_issues],
            "suppressed": [issue.to_dict() for issue in self.suppressed],
        }


def plan_issue_filing(reports: Iterable[RepoReport]) -> IssueFilingPlan:
    plan = IssueFilingPlan()
    for report in reports:
        existing_titles = {_normalize(issue.title): issue for issue in report.open_issues}
        for recommendation in report.recommendations:
            _apply_recommendation(plan, report, recommendation, existing_titles)
    return plan


def render_issue_plan_json(plan: IssueFilingPlan) -> str:
    return json.dumps(plan.to_dict(), indent=2) + "\n"


def render_issue_plan_markdown(plan: IssueFilingPlan) -> str:
    lines = [
        "# Issue Filing Plan",
        "",
        "Dry run: yes",
        "",
        "## Proposed Issues",
        "",
    ]
    if plan.proposed_issues:
        for issue in plan.proposed_issues:
            lines.extend(
                [
                    f"### {issue.repo}: {issue.title}",
                    "",
                    f"Reason: {issue.reason}",
                    f"Confidence: {issue.confidence}",
                    "Requires confirmation: yes",
                    "",
                    "Body:",
                    "",
                    issue.body,
                    "",
                ]
            )
    else:
        lines.append("None.")
        lines.append("")

    lines.append("## Suppressed")
    lines.append("")
    if plan.suppressed:
        for item in plan.suppressed:
            detail = f" Existing: {item.existing_artifact}" if item.existing_artifact else ""
            lines.append(f"- {item.repo}: {item.title} -- {item.reason}.{detail}")
    else:
        lines.append("None.")
    return "\n".join(lines).rstrip() + "\n"


def _apply_recommendation(
    plan: IssueFilingPlan,
    report: RepoReport,
    recommendation: Recommendation,
    existing_titles: Dict[str, object],
) -> None:
    if recommendation.local_only:
        plan.suppressed.append(
            SuppressedIssue(
                repo=report.name,
                title=recommendation.title,
                reason="local-only hygiene should not become a public GitHub issue",
                local_only=True,
            )
        )
        return

    if recommendation.kind == "review_existing_artifact" or recommendation.github_artifact:
        plan.suppressed.append(
            SuppressedIssue(
                repo=report.name,
                title=recommendation.title,
                reason="existing GitHub artifact should be reviewed before filing a duplicate",
                existing_artifact=recommendation.github_artifact,
            )
        )
        return

    if recommendation.kind != "public_repo_work":
        plan.suppressed.append(
            SuppressedIssue(
                repo=report.name,
                title=recommendation.title,
                reason=f"recommendation kind {recommendation.kind!r} is not fileable public repo work",
            )
        )
        return

    normalized = _normalize(recommendation.title)
    if normalized in existing_titles:
        existing = existing_titles[normalized]
        plan.suppressed.append(
            SuppressedIssue(
                repo=report.name,
                title=recommendation.title,
                reason="open issue with matching title already exists",
                existing_artifact=getattr(existing, "url", ""),
            )
        )
        return

    plan.proposed_issues.append(
        ProposedIssue(
            repo=report.name,
            title=recommendation.title,
            body=_issue_body(report, recommendation),
            reason=recommendation.reason,
            confidence=recommendation.confidence,
            source_recommendation_kind=recommendation.kind,
        )
    )


def _issue_body(report: RepoReport, recommendation: Recommendation) -> str:
    command = (
        f"\n\nSuggested safe next command:\n\n```bash\n{recommendation.safe_next_command}\n```"
        if recommendation.safe_next_command
        else ""
    )
    return (
        f"repo-steward proposed this issue from a dry-run audit recommendation.\n\n"
        f"Reason: {recommendation.reason}\n\n"
        f"Confidence: {recommendation.confidence}\n\n"
        f"Repository: {report.name}{command}\n\n"
        "Acceptance criteria:\n"
        "- Confirm the recommendation is still current.\n"
        "- Keep any fix narrowly scoped.\n"
        "- Add or update tests/docs when the public contract changes.\n"
        "- Verify with CI before merge.\n\n"
        "This issue was generated as a plan only; no GitHub mutation should happen without human confirmation."
    )


def _normalize(title: str) -> str:
    return re.sub(r"\s+", " ", title.strip().lower())
