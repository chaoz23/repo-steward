import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from repo_steward.cli import main
from repo_steward.github import audit_repo
from repo_steward.issue_plan import plan_issue_filing, render_issue_plan_json, render_issue_plan_markdown
from repo_steward.local import inspect_checkout
from repo_steward.model import Issue, LocalCheckout, PullRequest, Recommendation, RepoReport, SCHEMA_VERSION, UnanchoredRef, WorkflowRun
from repo_steward.refs import anchor_shas, candidate_heads, classify, parse_ls_remote
from repo_steward.recommend import recommend
from repo_steward.render import render_console, render_json, render_markdown, render_tracker


class RepoStewardTests(unittest.TestCase):
    def test_markdown_renders_portfolio_table_and_recommendation(self):
        report = RepoReport(
            name="chaoz23/example",
            url="https://github.com/chaoz23/example",
            open_issues=[Issue(1, "Fix docs", "https://github.com/chaoz23/example/issues/1")],
            open_prs=[],
            latest_run=WorkflowRun("CI", "completed", "success", "https://example.test/run"),
        )
        report.recommendations = recommend(report)

        text = render_markdown([report])

        self.assertIn("GitHub Portfolio Stewardship Report", text)
        self.assertIn("[chaoz23/example](https://github.com/chaoz23/example)", text)
        self.assertIn("CI: completed / success", text)
        self.assertIn("Fix docs", text)

    def test_recommendation_prioritizes_open_prs(self):
        report = RepoReport(
            name="chaoz23/example",
            url="",
            open_prs=[PullRequest(3, "Old branch", "https://example.test/pr/3")],
            latest_run=WorkflowRun("CI", "completed", "success", "https://example.test/run"),
        )

        recommendation = recommend(report)[0]
        self.assertEqual(recommendation.kind, "review_existing_artifact")
        self.assertTrue(recommendation.requires_confirmation)

    def test_cli_loads_json_fixture(self):
        data = {
            "repositories": [
                {
                    "name": "chaoz23/example",
                    "url": "https://github.com/chaoz23/example",
                    "open_issues": [],
                    "open_prs": [],
                    "latest_run": None,
                }
            ]
        }
        with tempfile.TemporaryDirectory() as tmp:
            fixture = Path(tmp) / "portfolio.json"
            output = Path(tmp) / "report.md"
            fixture.write_text(json.dumps(data), encoding="utf-8")

            code = main(["audit", "--from-json", str(fixture), "--out", str(output)])

            self.assertEqual(code, 0)
            self.assertIn("chaoz23/example", output.read_text(encoding="utf-8"))

    def test_issue_plan_proposes_fileable_public_repo_work(self):
        report = RepoReport(
            name="chaoz23/example",
            url="https://github.com/chaoz23/example",
            open_issues=[],
            recommendations=[
                Recommendation(
                    kind="public_repo_work",
                    title="Add CI smoke test",
                    confidence="high",
                    reason="CI does not exercise the command agents rely on.",
                    safe_next_command="python -m unittest",
                )
            ],
        )

        plan = plan_issue_filing([report])
        data = json.loads(render_issue_plan_json(plan))
        markdown = render_issue_plan_markdown(plan)

        self.assertTrue(data["dry_run"])
        self.assertEqual(data["proposed_issues"][0]["repo"], "chaoz23/example")
        self.assertEqual(data["proposed_issues"][0]["title"], "Add CI smoke test")
        self.assertIn("Acceptance criteria", data["proposed_issues"][0]["body"])
        self.assertIn("python -m unittest", data["proposed_issues"][0]["body"])
        self.assertIn("chaoz23/example: Add CI smoke test", markdown)

    def test_issue_plan_suppresses_duplicate_open_issue_titles(self):
        report = RepoReport(
            name="chaoz23/example",
            url="",
            open_issues=[
                Issue(7, "Add CI smoke test", "https://github.com/chaoz23/example/issues/7")
            ],
            recommendations=[
                Recommendation(
                    kind="public_repo_work",
                    title="  add   ci smoke TEST ",
                    confidence="high",
                    reason="Same work is already tracked.",
                )
            ],
        )

        plan = plan_issue_filing([report])

        self.assertEqual(plan.proposed_issues, [])
        self.assertEqual(plan.suppressed[0].reason, "open issue with matching title already exists")
        self.assertEqual(plan.suppressed[0].existing_artifact, "https://github.com/chaoz23/example/issues/7")

    def test_issue_plan_suppresses_local_only_recommendations(self):
        report = RepoReport(
            name="chaoz23/example",
            url="",
            recommendations=[
                Recommendation(
                    kind="local_hygiene",
                    title="Resolve untracked local file",
                    confidence="high",
                    reason="The checkout has local-only residue.",
                    local_only=True,
                )
            ],
        )

        plan = plan_issue_filing([report])

        self.assertEqual(plan.proposed_issues, [])
        self.assertTrue(plan.suppressed[0].local_only)

    def test_cli_file_issues_writes_dry_run_json_plan(self):
        data = {
            "repositories": [
                {
                    "name": "chaoz23/example",
                    "url": "https://github.com/chaoz23/example",
                    "open_issues": [],
                    "open_prs": [],
                    "latest_run": None,
                    "recommendations": [
                        {
                            "kind": "public_repo_work",
                            "title": "Document release flow",
                            "confidence": "medium",
                            "reason": "Release expectations are not documented.",
                        }
                    ],
                }
            ]
        }
        with tempfile.TemporaryDirectory() as tmp:
            fixture = Path(tmp) / "portfolio.json"
            output = Path(tmp) / "issue-plan.json"
            fixture.write_text(json.dumps(data), encoding="utf-8")

            code = main(
                [
                    "file-issues",
                    "--dry-run",
                    "--from-json",
                    str(fixture),
                    "--format",
                    "json",
                    "--out",
                    str(output),
                ]
            )

            plan = json.loads(output.read_text(encoding="utf-8"))
            self.assertEqual(code, 0)
            self.assertEqual(plan["proposed_issues"][0]["title"], "Document release flow")
            self.assertEqual(plan["suppressed"], [])

    def test_cli_file_issues_without_dry_run_is_blocked(self):
        data = {
            "repositories": [
                {
                    "name": "chaoz23/example",
                    "url": "https://github.com/chaoz23/example",
                    "open_issues": [],
                    "open_prs": [],
                    "latest_run": None,
                }
            ]
        }
        with tempfile.TemporaryDirectory() as tmp:
            fixture = Path(tmp) / "portfolio.json"
            fixture.write_text(json.dumps(data), encoding="utf-8")

            code = main(["file-issues", "--from-json", str(fixture)])

            self.assertEqual(code, 2)

    def test_cli_daily_writes_timestamped_read_only_artifacts(self):
        data = {
            "repositories": [
                {
                    "name": "chaoz23/example",
                    "url": "https://github.com/chaoz23/example",
                    "open_issues": [
                        {
                            "number": 7,
                            "title": "Document release flow",
                            "url": "https://github.com/chaoz23/example/issues/7",
                        }
                    ],
                    "open_prs": [],
                    "latest_run": {
                        "workflowName": "CI",
                        "status": "completed",
                        "conclusion": "success",
                        "url": "https://example.test/run",
                    },
                    "recommendations": [
                        {
                            "kind": "public_repo_work",
                            "title": "Document release flow",
                            "confidence": "medium",
                            "reason": "Release expectations are not documented.",
                        }
                    ],
                }
            ]
        }
        with tempfile.TemporaryDirectory() as tmp:
            fixture = Path(tmp) / "portfolio.json"
            out_dir = Path(tmp) / "daily"
            fixture.write_text(json.dumps(data), encoding="utf-8")

            code = main(
                [
                    "daily",
                    "--from-json",
                    str(fixture),
                    "--out-dir",
                    str(out_dir),
                    "--date",
                    "2026-07-21",
                ]
            )

            self.assertEqual(code, 0)
            audit = json.loads((out_dir / "2026-07-21-audit.json").read_text(encoding="utf-8"))
            tracker = (out_dir / "2026-07-21-tracker.md").read_text(encoding="utf-8")
            issue_plan = (out_dir / "2026-07-21-issue-plan.md").read_text(encoding="utf-8")
            summary = (out_dir / "2026-07-21-summary.md").read_text(encoding="utf-8")
            self.assertEqual(audit["repositories"][0]["name"], "chaoz23/example")
            self.assertIn("GitHub Work Tracker", tracker)
            self.assertIn("open issue with matching title already exists", issue_plan)
            self.assertIn("No GitHub mutations were attempted.", summary)

    def test_json_has_schema_version_and_structured_recommendation(self):
        report = RepoReport(name="chaoz23/example", url="", open_issues=[])
        report.recommendations = recommend(report)

        data = json.loads(render_json([report]))

        self.assertEqual(data["schema_version"], SCHEMA_VERSION)
        item = data["repositories"][0]["recommendations"][0]
        self.assertEqual(item["kind"], "public_repo_work")
        self.assertIn("requires_confirmation", item)

    def test_tracker_and_console_render_agent_handoff_surfaces(self):
        report = RepoReport(
            name="chaoz23/example",
            url="https://github.com/chaoz23/example",
            open_issues=[Issue(1, "Fix docs", "https://example.test/1")],
            latest_run=WorkflowRun("CI", "completed", "success", "https://example.test/run"),
            local_checkout=LocalCheckout(
                path="/tmp/example",
                branch="main",
                synced_with_upstream=True,
                status="clean",
            ),
        )
        report.recommendations = recommend(report)

        tracker = render_tracker([report])
        console = render_console([report])

        self.assertIn("GitHub Work Tracker", tracker)
        self.assertIn("chaoz23/example", tracker)
        self.assertIn("REPOSITORY", console)
        self.assertIn("success", console)

    def test_local_checkout_classifies_untracked_files_as_local_hygiene(self):
        with tempfile.TemporaryDirectory() as tmp:
            checkout = Path(tmp)
            (checkout / "note.txt").write_text("local\n", encoding="utf-8")
            import subprocess

            subprocess.run(["git", "init", "-b", "main"], cwd=tmp, check=True, stdout=subprocess.PIPE)

            local = inspect_checkout(tmp)

        self.assertEqual(local.status, "local_hygiene")
        self.assertEqual(local.untracked_files, 1)

    def test_audit_repo_uses_gh_outputs(self):
        responses = [
            {
                "nameWithOwner": "chaoz23/example",
                "url": "https://github.com/chaoz23/example",
                "description": "demo",
                "visibility": "PUBLIC",
                "defaultBranchRef": {"name": "main"},
            },
            [{"number": 1, "title": "Fix docs", "url": "https://example.test/issue/1"}],
            [{"number": 2, "title": "Draft work", "url": "https://example.test/pr/2", "isDraft": True}],
            [{"workflowName": "CI", "status": "completed", "conclusion": "success", "url": "https://example.test/run"}],
        ]

        with patch("repo_steward.github._run_gh", side_effect=responses):
            report = audit_repo("chaoz23/example")

        self.assertEqual(report.name, "chaoz23/example")
        self.assertEqual(report.open_issues[0].title, "Fix docs")
        self.assertTrue(report.open_prs[0].is_draft)
        self.assertEqual(report.latest_run.conclusion, "success")


class RefProvenanceGateTests(unittest.TestCase):
    """The predicate that would have caught the 2026-10-20 near-miss.

    A branch is safe to delete only when GitHub holds an immutable copy of its
    tip: the default branch, a tag, or refs/pull/N/head.
    """

    DEFAULT = "main"

    def _ls_remote(self, *lines):
        return parse_ls_remote("\n".join(lines) + "\n")

    def test_parse_handles_tabs_and_blank_lines(self):
        pairs = parse_ls_remote("aaa\trefs/heads/main\n\nbbb\trefs/tags/v1\n")
        self.assertEqual(pairs, [("aaa", "refs/heads/main"), ("bbb", "refs/tags/v1")])

    def test_pull_ref_anchors_a_branch(self):
        # The 89 branches deleted on 2026-10-20: every tip was a PR head.
        pairs = self._ls_remote(
            "d00\trefs/heads/main",
            "a02\trefs/heads/agent/release-contract-p0",
            "a02\trefs/pull/43/head",
        )
        self.assertIn("a02", anchor_shas(pairs))
        self.assertEqual(classify(pairs, self.DEFAULT), [])

    def test_peeled_annotated_tag_anchors_a_branch(self):
        # An annotated tag advertises both the tag object and the peeled commit.
        pairs = self._ls_remote(
            "d00\trefs/heads/main",
            "b85\trefs/heads/benchmark/evidence",
            "1a4\trefs/tags/inkbench-2026-08-evidence",
            "b85\trefs/tags/inkbench-2026-08-evidence^{}",
        )
        self.assertEqual(classify(pairs, self.DEFAULT), [])

    def test_reachable_from_default_anchors_a_branch(self):
        pairs = self._ls_remote(
            "d00\trefs/heads/main",
            "c01\trefs/heads/already-merged",
        )
        self.assertEqual(classify(pairs, self.DEFAULT, {"c01": True}), [])

    def test_branch_with_no_anchor_is_reported(self):
        # chaoz23/inkbench codex/heresy-planted: no PR, no tag, not on main.
        pairs = self._ls_remote(
            "d00\trefs/heads/main",
            "163\trefs/heads/codex/heresy-planted",
            "9d4\trefs/pull/10/head",
            "e03\trefs/tags/v0.3.0",
        )
        found = classify(pairs, self.DEFAULT, {"163": False})
        self.assertEqual([item.branch for item in found], ["codex/heresy-planted"])
        self.assertEqual(found[0].tip, "163")
        self.assertIn("only copy", found[0].reason)

    def test_unknown_reachability_over_reports_rather_than_under_reports(self):
        # A failed comparison must never be read as "safe to delete".
        pairs = self._ls_remote(
            "d00\trefs/heads/main",
            "xyz\trefs/heads/mystery",
        )
        self.assertEqual([i.branch for i in classify(pairs, self.DEFAULT)], ["mystery"])
        self.assertEqual([i.branch for i in classify(pairs, self.DEFAULT, {"xyz": None})], ["mystery"])

    def test_default_branch_is_never_a_candidate(self):
        pairs = self._ls_remote("d00\trefs/heads/main")
        self.assertEqual(candidate_heads(pairs, self.DEFAULT), [])
        self.assertEqual(classify(pairs, self.DEFAULT), [])

    def test_non_default_trunk_name_is_respected(self):
        pairs = self._ls_remote("d00\trefs/heads/master", "f01\trefs/heads/side")
        self.assertEqual([b for _, b in candidate_heads(pairs, "master")], ["side"])

    def test_results_are_sorted_for_stable_reports(self):
        pairs = self._ls_remote(
            "d00\trefs/heads/main", "s01\trefs/heads/zeta", "s02\trefs/heads/alpha"
        )
        self.assertEqual([i.branch for i in classify(pairs, self.DEFAULT)], ["alpha", "zeta"])

    def test_recommendation_leads_with_irreversible_risk(self):
        report = RepoReport(
            name="chaoz23/inkbench",
            url="https://github.com/chaoz23/inkbench",
            open_prs=[PullRequest(number=1, title="t", url="u")],
            unanchored_refs=[
                UnanchoredRef("refs/heads/codex/heresy-planted", "codex/heresy-planted", "163ecb32", "no anchor")
            ],
        )
        items = recommend(report)
        self.assertEqual(items[0].kind, "irreversible_risk")
        self.assertTrue(items[0].requires_confirmation)
        self.assertIn("codex/heresy-planted", items[0].title)

    def test_no_unanchored_refs_produces_no_risk_recommendation(self):
        report = RepoReport(name="chaoz23/clean", url="")
        self.assertNotIn("irreversible_risk", [item.kind for item in recommend(report)])

    def test_json_round_trip_preserves_unanchored_refs(self):
        report = RepoReport(
            name="chaoz23/inkbench",
            url="",
            unanchored_refs=[UnanchoredRef("refs/heads/x", "x", "abc123", "why")],
        )
        restored = RepoReport.from_dict(json.loads(render_json([report]))["repositories"][0])
        self.assertEqual(restored.unanchored_refs[0].tip, "abc123")
        self.assertEqual(restored.unanchored_refs[0].branch, "x")

    def test_schema_without_the_field_still_loads(self):
        self.assertEqual(RepoReport.from_dict({"name": "a/b"}).unanchored_refs, [])

    def test_markdown_and_console_surface_the_count(self):
        report = RepoReport(
            name="chaoz23/inkbench",
            url="",
            unanchored_refs=[UnanchoredRef("refs/heads/x", "x", "abcdef123", "why")],
        )
        report.recommendations = recommend(report)
        self.assertIn("Unanchored refs", render_markdown([report]))
        self.assertIn("abcdef123"[:9], render_markdown([report]))
        self.assertIn("UNANCH", render_console([report]))


if __name__ == "__main__":
    unittest.main()
