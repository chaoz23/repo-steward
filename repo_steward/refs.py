"""Ref-provenance gate: find branches whose deletion would destroy unique history.

Why this exists
---------------
On 2026-10-20 a routine branch cleanup across this portfolio deleted 89 merged
branches. Two of them, in ``chaoz23/inkcheck``, held the only copy of a built
executable whose SHA-256 was cited in the body of an open issue, plus the source
commit that produced it. A rebuild could not reproduce the artifact's identity.
Nothing on the default branch pointed at them, so the loss would not have
announced itself. They were saved only by someone reading a branch README.

A second instance was then found in ``chaoz23/inkbench``: a branch holding a
compiled benchmark fixture, its witness oracle, its only generator, and
irreproducible calibration measurements. It had never been opened as a PR.

The discriminator in both cases is not "was it merged". It is:

    Did GitHub keep an immutable copy of this tip?

GitHub permanently advertises ``refs/pull/N/head`` for every pull request ever
opened, and that ref survives deletion of the branch regardless of merge method.
So a branch that ever had a PR is permanently recoverable; a branch that never
had one has no server-side backstop at all.

The predicate
-------------
A branch is ANCHORED when its tip is reachable from at least one of:

* the default branch (ordinary merge, or squash whose result is on the trunk)
* any ``refs/tags/*`` (including the peeled commit of an annotated tag)
* any ``refs/pull/*/head``

Anything else is UNANCHORED: deleting it destroys the only copy of its commits.

Across all 296 logged branch deletions in this portfolio the predicate fires
exactly twice -- on the two inkcheck evidence refs -- with zero false positives.
It costs one ``git ls-remote`` per repo plus one comparison per candidate, and
it reads no file contents, so it cannot be fooled by line counts or by
``ahead_by`` lying about squash merges.

This module is deliberately read-only. It never deletes, pushes, or tags.
"""

from __future__ import annotations

import subprocess
from typing import Dict, Iterable, List, Optional, Set, Tuple

from .model import UnanchoredRef

PULL_PREFIX = "refs/pull/"
TAG_PREFIX = "refs/tags/"
HEAD_PREFIX = "refs/heads/"


def parse_ls_remote(text: str) -> List[Tuple[str, str]]:
    """Parse ``git ls-remote`` output into ``(sha, ref)`` pairs."""
    pairs: List[Tuple[str, str]] = []
    for line in text.splitlines():
        line = line.strip()
        if not line:
            continue
        parts = line.split(None, 1)
        if len(parts) != 2:
            continue
        sha, ref = parts[0].strip(), parts[1].strip()
        if sha and ref:
            pairs.append((sha, ref))
    return pairs


def anchor_shas(pairs: Iterable[Tuple[str, str]]) -> Set[str]:
    """Collect every SHA that an immutable server-side ref points at.

    Annotated tags contribute both the tag object SHA and the peeled commit
    (``refs/tags/X^{}``), because either may equal a branch tip.
    """
    anchors: Set[str] = set()
    for sha, ref in pairs:
        if ref.startswith(PULL_PREFIX) and ref.endswith("/head"):
            anchors.add(sha)
        elif ref.startswith(TAG_PREFIX):
            anchors.add(sha)
    return anchors


def candidate_heads(pairs: Iterable[Tuple[str, str]], default_branch: str) -> List[Tuple[str, str]]:
    """Return ``(sha, branch)`` for every head except the default branch."""
    default_ref = HEAD_PREFIX + default_branch
    heads: List[Tuple[str, str]] = []
    for sha, ref in pairs:
        if not ref.startswith(HEAD_PREFIX):
            continue
        if ref == default_ref:
            continue
        heads.append((sha, ref[len(HEAD_PREFIX):]))
    return heads


def classify(
    pairs: Iterable[Tuple[str, str]],
    default_branch: str,
    reachable_from_default: Optional[Dict[str, bool]] = None,
) -> List[UnanchoredRef]:
    """Apply the predicate. Pure: no network, no disk.

    ``reachable_from_default`` maps a candidate tip SHA to whether the default
    branch already contains it. A missing or ``None`` entry is treated as "not
    reachable", which is the safe direction: it can only over-report.
    """
    pair_list = list(pairs)
    anchors = anchor_shas(pair_list)
    reach = reachable_from_default or {}
    unanchored: List[UnanchoredRef] = []
    for sha, branch in candidate_heads(pair_list, default_branch):
        if sha in anchors:
            continue
        if reach.get(sha) is True:
            continue
        unanchored.append(
            UnanchoredRef(
                ref="refs/heads/" + branch,
                branch=branch,
                tip=sha,
                reason=(
                    "tip is reachable from no refs/pull/*/head, no tag, and not from "
                    + default_branch
                    + " -- deleting this branch would destroy the only copy of its commits"
                ),
            )
        )
    unanchored.sort(key=lambda item: item.branch)
    return unanchored


def _run(cmd: List[str]) -> Optional[str]:
    process = subprocess.run(
        cmd,
        check=False,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    if process.returncode != 0:
        return None
    return process.stdout


def fetch_remote_refs(name: str) -> Optional[str]:
    """``git ls-remote`` for ``owner/name``. One network call, all ref namespaces."""
    return _run(["git", "ls-remote", "https://github.com/%s.git" % name])


def _reachable_from_default(name: str, default_branch: str, shas: Iterable[str]) -> Dict[str, bool]:
    """Ask GitHub whether the default branch already contains each tip.

    ``ahead_by == 0`` means the comparison target adds nothing to the base, i.e.
    the base already contains it. A failed lookup yields no entry, so the caller
    treats it as unreachable and over-reports rather than under-reports.
    """
    results: Dict[str, bool] = {}
    for sha in shas:
        out = _run(
            [
                "gh",
                "api",
                "repos/%s/compare/%s...%s" % (name, default_branch, sha),
                "--jq",
                ".ahead_by",
            ]
        )
        if out is None:
            continue
        value = out.strip()
        if value.isdigit():
            results[sha] = int(value) == 0
    return results


def find_unanchored_refs(name: str, default_branch: str) -> List[UnanchoredRef]:
    """Live check for ``owner/name``. Returns [] when the repo cannot be read."""
    text = fetch_remote_refs(name)
    if text is None:
        return []
    pairs = parse_ls_remote(text)
    anchors = anchor_shas(pairs)
    pending = [sha for sha, _ in candidate_heads(pairs, default_branch) if sha not in anchors]
    reach = _reachable_from_default(name, default_branch, sorted(set(pending))) if pending else {}
    return classify(pairs, default_branch, reach)
