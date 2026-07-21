from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


SCHEMA_VERSION = "1.0"


@dataclass
class Issue:
    number: int
    title: str
    url: str

    @classmethod
    def from_gh(cls, data: Dict[str, Any]) -> "Issue":
        return cls(
            number=int(data["number"]),
            title=str(data["title"]),
            url=str(data["url"]),
        )

    def to_dict(self) -> Dict[str, Any]:
        return {"number": self.number, "title": self.title, "url": self.url}


@dataclass
class PullRequest:
    number: int
    title: str
    url: str
    is_draft: bool = False

    @classmethod
    def from_gh(cls, data: Dict[str, Any]) -> "PullRequest":
        return cls(
            number=int(data["number"]),
            title=str(data["title"]),
            url=str(data["url"]),
            is_draft=bool(data.get("isDraft", False)),
        )

    def to_dict(self) -> Dict[str, Any]:
        return {
            "number": self.number,
            "title": self.title,
            "url": self.url,
            "is_draft": self.is_draft,
        }


@dataclass
class WorkflowRun:
    workflow_name: str
    status: str
    conclusion: Optional[str]
    url: str

    @classmethod
    def from_gh(cls, data: Dict[str, Any]) -> "WorkflowRun":
        return cls(
            workflow_name=str(data.get("workflowName") or data.get("name") or ""),
            status=str(data.get("status") or ""),
            conclusion=data.get("conclusion"),
            url=str(data.get("url") or ""),
        )

    def to_dict(self) -> Dict[str, Any]:
        return {
            "workflow_name": self.workflow_name,
            "status": self.status,
            "conclusion": self.conclusion,
            "url": self.url,
        }


@dataclass
class LocalCheckout:
    path: str
    branch: str = ""
    synced_with_upstream: Optional[bool] = None
    tracked_changes: int = 0
    untracked_files: int = 0
    status: str = "unknown"
    notes: List[str] = field(default_factory=list)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "LocalCheckout":
        return cls(
            path=str(data.get("path") or ""),
            branch=str(data.get("branch") or ""),
            synced_with_upstream=data.get("synced_with_upstream"),
            tracked_changes=int(data.get("tracked_changes") or 0),
            untracked_files=int(data.get("untracked_files") or 0),
            status=str(data.get("status") or "unknown"),
            notes=[str(item) for item in data.get("notes", [])],
        )

    def to_dict(self) -> Dict[str, Any]:
        return {
            "path": self.path,
            "branch": self.branch,
            "synced_with_upstream": self.synced_with_upstream,
            "tracked_changes": self.tracked_changes,
            "untracked_files": self.untracked_files,
            "status": self.status,
            "notes": list(self.notes),
        }


@dataclass
class Recommendation:
    kind: str
    title: str
    confidence: str
    reason: str
    safe_next_command: str = ""
    requires_confirmation: bool = False
    github_artifact: str = ""
    local_only: bool = False

    @classmethod
    def from_dict(cls, data: Any) -> "Recommendation":
        if isinstance(data, str):
            return cls(
                kind="general",
                title=data,
                confidence="medium",
                reason=data,
            )
        return cls(
            kind=str(data.get("kind") or "general"),
            title=str(data.get("title") or ""),
            confidence=str(data.get("confidence") or "medium"),
            reason=str(data.get("reason") or ""),
            safe_next_command=str(data.get("safe_next_command") or ""),
            requires_confirmation=bool(data.get("requires_confirmation", False)),
            github_artifact=str(data.get("github_artifact") or ""),
            local_only=bool(data.get("local_only", False)),
        )

    def to_dict(self) -> Dict[str, Any]:
        return {
            "kind": self.kind,
            "title": self.title,
            "confidence": self.confidence,
            "reason": self.reason,
            "safe_next_command": self.safe_next_command,
            "requires_confirmation": self.requires_confirmation,
            "github_artifact": self.github_artifact,
            "local_only": self.local_only,
        }


@dataclass
class RepoReport:
    name: str
    url: str
    description: str = ""
    visibility: str = ""
    default_branch: str = "main"
    open_issues: List[Issue] = field(default_factory=list)
    open_prs: List[PullRequest] = field(default_factory=list)
    latest_run: Optional[WorkflowRun] = None
    local_checkout: Optional[LocalCheckout] = None
    errors: List[str] = field(default_factory=list)
    recommendations: List[Recommendation] = field(default_factory=list)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "RepoReport":
        latest = data.get("latest_run")
        local = data.get("local_checkout")
        return cls(
            name=str(data["name"]),
            url=str(data.get("url") or ""),
            description=str(data.get("description") or ""),
            visibility=str(data.get("visibility") or ""),
            default_branch=str(data.get("default_branch") or "main"),
            open_issues=[Issue.from_gh(item) for item in data.get("open_issues", [])],
            open_prs=[PullRequest.from_gh(item) for item in data.get("open_prs", [])],
            latest_run=WorkflowRun.from_gh(latest) if latest else None,
            local_checkout=LocalCheckout.from_dict(local) if local else None,
            errors=[str(item) for item in data.get("errors", [])],
            recommendations=[
                Recommendation.from_dict(item) for item in data.get("recommendations", [])
            ],
        )

    def to_dict(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "url": self.url,
            "description": self.description,
            "visibility": self.visibility,
            "default_branch": self.default_branch,
            "open_issues": [item.to_dict() for item in self.open_issues],
            "open_prs": [item.to_dict() for item in self.open_prs],
            "latest_run": self.latest_run.to_dict() if self.latest_run else None,
            "local_checkout": self.local_checkout.to_dict() if self.local_checkout else None,
            "errors": list(self.errors),
            "recommendations": [item.to_dict() for item in self.recommendations],
        }

