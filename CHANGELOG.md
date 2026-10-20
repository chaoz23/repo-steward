# Changelog

## 0.5.0 - 2026-10-20

- Add a ref-provenance gate: flag branches whose tip is reachable from no
  `refs/pull/*/head`, no tag, and not from the default branch. Deleting such a
  branch destroys the only copy of its commits.
- Report unanchored refs in the audit JSON (`unanchored_refs`, schema 1.1), the
  markdown report, and the console summary.
- Emit a high-confidence `irreversible_risk` recommendation, ranked first, when
  any unanchored ref is present.
- Rationale: a cleanup on 2026-10-20 deleted 89 merged branches safely, but two
  branches in `inkcheck` held the only copy of a build artifact whose SHA-256 is
  cited in an open issue, and one in `inkbench` held a compiled benchmark
  fixture, its only generator, and irreproducible calibration data. Merge status
  and line counts do not establish deletion safety; ref reachability does.

## 0.4.0 - 2026-07-21

- Add `repo-steward daily` for read-only scheduled portfolio snapshots.
- Write dated audit JSON, tracker, dry-run issue plan, and summary artifacts to one output directory.
- Document a safe daily cron shape that surfaces work without mutating GitHub.

## 0.3.0 - 2026-07-21

- Add dry-run issue filing plans with `repo-steward file-issues --dry-run`.
- Propose issue titles and bodies from structured audit recommendations.
- Suppress local-only recommendations, existing GitHub artifacts, and duplicate open issue titles.
- Keep GitHub mutation unavailable by default.

## 0.2.0 - 2026-07-21

- Add versioned JSON output with `schema_version`.
- Replace string recommendations with structured recommendation objects.
- Add `--format tracker` for `GITHUB_WORK.md`-style continuity output.
- Add `--format console` for a compact terminal summary.
- Add optional local checkout hygiene classification with `--with-local-checkouts`.
- Keep mutation commands blocked in v0-style safety posture.

## 0.1.0 - 2026-07-21

- Bootstrap audit-only `repo-steward` CLI.
- Add Markdown and JSON report rendering.
- Add GitHub reads through `gh`.
- Add tests, README, license, and CI.
