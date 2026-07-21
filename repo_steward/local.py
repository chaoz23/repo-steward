from __future__ import annotations

import subprocess
from pathlib import Path
from typing import Dict, Optional

from .model import LocalCheckout


def inspect_checkout(path: str) -> LocalCheckout:
    checkout = Path(path)
    if not checkout.exists():
        return LocalCheckout(path=path, status="missing", notes=["checkout path does not exist"])
    if not (checkout / ".git").exists():
        return LocalCheckout(path=path, status="not_git", notes=["path is not a git checkout"])

    branch = _git(checkout, ["branch", "--show-current"]) or ""
    upstream = _git(checkout, ["rev-parse", "--abbrev-ref", "--symbolic-full-name", "@{u}"])
    ahead_behind = _git(checkout, ["rev-list", "--left-right", "--count", "HEAD...@{u}"])
    tracked = 0
    untracked = 0
    notes = []

    status = _git(checkout, ["status", "--porcelain"]) or ""
    for line in status.splitlines():
        if line.startswith("??"):
            untracked += 1
        else:
            tracked += 1

    synced: Optional[bool] = None
    if upstream and ahead_behind:
        parts = ahead_behind.split()
        if len(parts) == 2:
            synced = parts == ["0", "0"]
            if parts[0] != "0":
                notes.append(f"local branch is {parts[0]} commit(s) ahead")
            if parts[1] != "0":
                notes.append(f"local branch is {parts[1]} commit(s) behind")
    elif not upstream:
        notes.append("no upstream branch configured")

    if tracked:
        notes.append(f"{tracked} tracked change(s)")
    if untracked:
        notes.append(f"{untracked} untracked file(s)")

    state = "clean"
    if tracked:
        state = "tracked_changes"
    elif untracked:
        state = "local_hygiene"
    elif synced is False:
        state = "stale_branch"
    elif synced is None:
        state = "unknown"

    return LocalCheckout(
        path=str(checkout),
        branch=branch,
        synced_with_upstream=synced,
        tracked_changes=tracked,
        untracked_files=untracked,
        status=state,
        notes=notes,
    )


def inspect_checkouts_by_repo(base_path: Optional[str]) -> Dict[str, LocalCheckout]:
    if not base_path:
        return {}
    base = Path(base_path)
    if not base.exists():
        return {}
    result: Dict[str, LocalCheckout] = {}
    for child in sorted(base.iterdir()):
        if child.is_dir() and (child / ".git").exists():
            result[child.name] = inspect_checkout(str(child))
    return result


def _git(path: Path, args: list) -> Optional[str]:
    process = subprocess.run(
        ["git", *args],
        cwd=str(path),
        check=False,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    if process.returncode != 0:
        return None
    return process.stdout.strip()
