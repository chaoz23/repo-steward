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
  --repo chaoz23/inkcheck \
  --repo chaoz23/loudcheck \
  --format markdown \
  --out GITHUB_WORK.md
```

For test fixtures or agent handoff data:

```bash
repo-steward audit --from-json portfolio.json --format markdown
```

## Current Scope

`repo-steward audit` collects:

- repository metadata;
- open issues;
- open pull requests;
- latest default-branch workflow run;
- conservative next-action recommendations.

Mutation commands are deliberately not implemented in v0. They should remain human-gated:

- `file-issues`
- `open-pr`
- `verify-pr`
- `merge-green`

## Output Contract

`repo-steward audit` supports:

- `--format markdown`: a compact portfolio table and per-repo notes;
- `--format json`: machine-readable report data;
- `--out PATH`: write output to a file instead of stdout.

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

## Development

```bash
python -m unittest discover -s tests -p 'test_*.py'
python -m repo_steward --help
```
