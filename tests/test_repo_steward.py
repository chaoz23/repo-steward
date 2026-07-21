import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from repo_steward.cli import main
from repo_steward.github import audit_repo
from repo_steward.model import Issue, PullRequest, RepoReport, WorkflowRun
from repo_steward.recommend import recommend
from repo_steward.render import render_markdown


class RepoStewardTests(unittest.TestCase):
    def test_markdown_renders_portfolio_table_and_recommendation(self):
        report = RepoReport(
            name="chaoz23/example",
            url="https://github.com/chaoz23/example",
            open_issues=[Issue(1, "Fix docs", "https://github.com/chaoz23/example/issues/1")],
            open_prs=[],
            latest_run=WorkflowRun("CI", "completed", "success", "https://example.test/run"),
            recommendations=["Choose the smallest high-trust issue already filed."],
        )

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

        self.assertEqual(
            recommend(report)[0],
            "Review open pull requests before filing overlapping issues.",
        )

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


if __name__ == "__main__":
    unittest.main()

