import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT))

from scripts.verify_github_actions_oidc_claims import (
    REPOSITORY,
    WORKFLOW_NAME,
    WORKFLOW_REF,
    validate_bound_claims,
)
from aigc_oidc_identity import IdentityVerificationError


class GitHubOIDCClaimBindingTests(unittest.TestCase):
    def setUp(self):
        self.source_sha = "a" * 40
        self.workflow_sha = "b" * 40
        self.claims = {
            "repository": REPOSITORY,
            "repository_id": "1287333065",
            "ref": "refs/heads/main",
            "workflow": WORKFLOW_NAME,
            "workflow_ref": WORKFLOW_REF,
            "workflow_sha": self.workflow_sha,
            "sha": self.source_sha,
            "event_name": "push",
            "run_id": "123456",
            "run_attempt": "1",
        }

    def test_workflow_sha_is_bound_separately_from_source_sha(self):
        validate_bound_claims(
            self.claims,
            expected_sha=self.source_sha,
            expected_workflow_sha=self.workflow_sha,
            expected_run_id="123456",
            expected_run_attempt="1",
        )

    def test_wrong_workflow_sha_blocks(self):
        with self.assertRaisesRegex(IdentityVerificationError, "oidc_claim_mismatch:workflow_sha"):
            validate_bound_claims(
                self.claims,
                expected_sha=self.source_sha,
                expected_workflow_sha="c" * 40,
                expected_run_id="123456",
                expected_run_attempt="1",
            )

    def test_wrong_source_sha_still_blocks(self):
        with self.assertRaisesRegex(IdentityVerificationError, "oidc_claim_mismatch:sha"):
            validate_bound_claims(
                self.claims,
                expected_sha="d" * 40,
                expected_workflow_sha=self.workflow_sha,
                expected_run_id="123456",
                expected_run_attempt="1",
            )

    def test_invalid_expected_workflow_sha_blocks(self):
        with self.assertRaisesRegex(IdentityVerificationError, "invalid_expected_workflow_sha"):
            validate_bound_claims(
                self.claims,
                expected_sha=self.source_sha,
                expected_workflow_sha="not-a-sha",
                expected_run_id="123456",
                expected_run_attempt="1",
            )


if __name__ == "__main__":
    unittest.main()
