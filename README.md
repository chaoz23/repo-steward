# repo-steward

`repo-steward` is a safety-first CLI for agent-assisted GitHub portfolio maintenance.

It does not replace GitHub. It wraps GitHub's existing lifecycle primitives into a boring, auditable workflow:

- Issues are the durable backlog.
- Pull requests are the mutation record.
- Actions are the verification harness.
- A local continuity file records what future agents need to know.

The first version is intentionally audit-only. It helps answer: what is the state of this repo portfolio, what deserves an issue, what is already tracked, and what is just local workspace hygiene?

## Install

```bash
python -m pip install -e .
```

The live GitHub audit path shells out to the GitHub CLI, so `gh` must be installed and authenticated for private repositories or write-capable future workflows.

## Quickstart

```bash
repo-steward audit \
  --portfolio repos.txt \
  --with-local-checkouts work/repos \
  --format tracker \
  --out GITHUB_WORK.md
```

For test fixtures or agent handoff data:

```bash
repo-steward audit --from-json portfolio.json --format markdown
```

For a daily read-only cron run:

```bash
repo-steward daily \
  --portfolio repos.txt \
  --with-local-checkouts work/repos \
  --out-dir reports
```

That writes dated `audit.json`, `tracker.md`, `issue-plan.md`, and `summary.md` artifacts. The issue plan is still dry-run only, so the daily job can surface work without creating public GitHub issues.

## Current Scope

`repo-steward audit` collects:

- repository metadata;
- open issues;
- open pull requests;
- latest default-branch workflow run;
- optional local checkout hygiene;
- conservative next-action recommendations.

Mutation commands are deliberately not implemented in v0. They should remain human-gated:

- `file-issues`
- `open-pr`
- `verify-pr`
- `merge-green`

`file-issues` now has a dry-run planner:

```bash
repo-steward file-issues --dry-run --from-json audit.json
```

It proposes issue titles and bodies from structured audit recommendations, suppresses duplicates from existing open issue titles, and never mutates GitHub.

## Output Contract

`repo-steward audit` supports:

- `--format markdown`: a compact portfolio table and per-repo notes;
- `--format json`: machine-readable report data;
- `--format tracker`: a compact `GITHUB_WORK.md`-style tracker;
- `--format console`: a thin terminal table;
- `--out PATH`: write output to a file instead of stdout.

`repo-steward daily` writes four dated files to `--out-dir`:

- `<date>-audit.json`: machine-readable audit data;
- `<date>-tracker.md`: `GITHUB_WORK.md`-style handoff table;
- `<date>-issue-plan.md`: dry-run issue filing plan;
- `<date>-summary.md`: compact counts and artifact links.

JSON output includes `schema_version` and structured recommendation objects with:

- `kind`;
- `title`;
- `confidence`;
- `reason`;
- `safe_next_command`;
- `requires_confirmation`;
- `github_artifact`;
- `local_only`.

Exit codes:

- `0`: report generated;
- `1`: one or more requested repositories could not be audited;
- `2`: invalid CLI usage or blocked mutation command.

## Safety Rules

- Audit is read-only.
- Mutations must be explicit subcommands and require confirmation.
- Existing issues or PRs win over duplicate filing.
- Local-only workspace hygiene should not become a public GitHub issue unless it reveals a reproducible repo policy gap.
- A repo with stale PRs should usually review or close the PR before filing another issue.
- Console/tracker output is a handoff surface, not an authorization to mutate GitHub.
- `file-issues` is dry-run only until a future release adds an explicit confirmation path.
- Daily cron runs should use `daily` or `audit`; they should not invoke mutation commands.

## Development

```bash
python -m unittest discover -s tests -p 'test_*.py'
python -m repo_steward --help
```
