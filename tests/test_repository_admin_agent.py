"""Automated unit tests for the read-only repository administrator agent.

These tests use mocked GitHub API responses. They validate decision logic only;
they do not prove live repository protection or cryptographic provenance.
Run: python -m unittest discover -s tests -p 'test_repository_admin_agent.py'
"""
import unittest
from unittest.mock import patch

import importlib.util
from pathlib import Path

SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "repository_admin_agent.py"
SPEC = importlib.util.spec_from_file_location("repository_admin_agent", SCRIPT)
agent = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(agent)


class RepositoryAdminAgentTests(unittest.TestCase):
    def test_missing_rulesets_and_unprotected_branch_fail_closed(self):
        def fake_get(repo, endpoint, token):
            if endpoint == "":
                return {"default_branch": "main", "private": False, "archived": False}
            if endpoint == "rulesets?includes_parents=true":
                return []
            if endpoint == "branches/main/protection":
                raise agent.GitHubReadError(404, endpoint, "Not Found")
            raise AssertionError(f"Unexpected endpoint: {endpoint}")

        with patch.object(agent, "github_get", side_effect=fake_get):
            report = agent.assess("Lornt1666/AIGC", None)

        self.assertEqual(report["decision"], "BLOCK")
        self.assertEqual(report["checks"]["rulesets"]["status"], "BLOCK")
        self.assertEqual(
            report["checks"]["branch_protection"]["status"],
            "UNKNOWN_NOT_FOUND_OR_HIDDEN",
        )
        self.assertEqual(report["checks"]["release_tag_protection"]["status"], "BLOCK")

    def test_api_permission_error_is_unknown_not_pass(self):
        def fake_get(repo, endpoint, token):
            if endpoint == "":
                return {"default_branch": "main"}
            raise agent.GitHubReadError(403, endpoint, "Forbidden")

        with patch.object(agent, "github_get", side_effect=fake_get):
            report = agent.assess("Lornt1666/AIGC", "read-only-token")

        self.assertEqual(report["decision"], "BLOCK")
        self.assertEqual(
            report["checks"]["rulesets"]["status"],
            "UNKNOWN_PERMISSION_OR_AUTH_ERROR",
        )
        self.assertEqual(
            report["checks"]["branch_protection"]["status"],
            "UNKNOWN_PERMISSION_OR_AUTH_ERROR",
        )

    def test_active_ruleset_alone_does_not_authorize_release(self):
        def fake_get(repo, endpoint, token):
            if endpoint == "":
                return {"default_branch": "main", "private": False}
            if endpoint == "rulesets?includes_parents=true":
                return [{
                    "id": 42,
                    "name": "protect main",
                    "enforcement": "active",
                    "target": "branch",
                    "conditions": {"ref_name": {
                        "include": ["refs/heads/main"], "exclude": []
                    }},
                    "rules": [{"type": "pull_request"}],
                    "bypass_actors": [],
                }]
            if endpoint == "branches/main/protection":
                return {
                    "required_pull_request_reviews": {
                        "required_approving_review_count": 1,
                        "dismiss_stale_reviews": True,
                        "require_code_owner_reviews": True,
                    },
                    "required_status_checks": {
                        "strict": True,
                        "contexts": ["canonical-validation"],
                    },
                    "enforce_admins": {"enabled": True},
                    "allow_force_pushes": {"enabled": False},
                    "allow_deletions": {"enabled": False},
                    "restrictions": None,
                }
            raise AssertionError(f"Unexpected endpoint: {endpoint}")

        with patch.object(agent, "github_get", side_effect=fake_get):
            report = agent.assess("Lornt1666/AIGC", None)

        self.assertEqual(report["checks"]["branch_protection"]["status"], "PASS")
        self.assertEqual(report["checks"]["release_tag_protection"]["status"], "BLOCK")
        self.assertEqual(report["decision"], "BLOCK")

    def test_unexpected_api_schema_does_not_pass(self):
        def fake_get(repo, endpoint, token):
            if endpoint == "":
                return {"default_branch": "main"}
            if endpoint == "rulesets?includes_parents=true":
                return {"unexpected": "schema"}
            if endpoint == "branches/main/protection":
                raise agent.GitHubReadError(404, endpoint, "Not Found")
            raise AssertionError(f"Unexpected endpoint: {endpoint}")

        with patch.object(agent, "github_get", side_effect=fake_get):
            report = agent.assess("Lornt1666/AIGC", None)

        self.assertEqual(report["decision"], "BLOCK")
        self.assertEqual(report["checks"]["rulesets"]["status"], "UNKNOWN_SCHEMA")
        self.assertEqual(report["checks"]["release_tag_protection"]["status"], "BLOCK")


if __name__ == "__main__":
    unittest.main()
