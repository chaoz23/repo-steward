from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


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
class RepoReport:
    name: str
    url: str
    description: str = ""
    visibility: str = ""
    default_branch: str = "main"
    open_issues: List[Issue] = field(default_factory=list)
    open_prs: List[PullRequest] = field(default_factory=list)
    latest_run: Optional[WorkflowRun] = None
    errors: List[str] = field(default_factory=list)
    recommendations: List[str] = field(default_factory=list)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "RepoReport":
        latest = data.get("latest_run")
        return cls(
            name=str(data["name"]),
            url=str(data.get("url") or ""),
            description=str(data.get("description") or ""),
            visibility=str(data.get("visibility") or ""),
            default_branch=str(data.get("default_branch") or "main"),
            open_issues=[Issue.from_gh(item) for item in data.get("open_issues", [])],
            open_prs=[PullRequest.from_gh(item) for item in data.get("open_prs", [])],
            latest_run=WorkflowRun.from_gh(latest) if latest else None,
            errors=[str(item) for item in data.get("errors", [])],
            recommendations=[str(item) for item in data.get("recommendations", [])],
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
            "errors": list(self.errors),
            "recommendations": list(self.recommendations),
        }

