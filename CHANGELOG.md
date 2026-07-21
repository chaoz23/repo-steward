# Changelog

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
