import unittest

from scripts.verify_github_actions_oidc_claims import (
    IdentityVerificationError,
    validate_bound_claims,
    REPOSITORY,
    REPOSITORY_ID,
    WORKFLOW_NAME,
    WORKFLOW_REF,
)

SHA = "a" * 40


def claims():
    return {
        "repository": REPOSITORY,
        "repository_id": REPOSITORY_ID,
        "ref": "refs/heads/main",
        "workflow": WORKFLOW_NAME,
        "workflow_ref": WORKFLOW_REF,
        "workflow_sha": SHA,
        "sha": SHA,
        "event_name": "push",
        "run_id": "12345",
        "run_attempt": "1",
    }


class GitHubOIDCClaimPolicyTests(unittest.TestCase):
    def test_exact_main_workflow_claims_pass(self):
        validate_bound_claims(claims(), expected_sha=SHA,
                              expected_workflow_sha=SHA, expected_run_id="12345", expected_run_attempt="1")

    def test_wrong_repository_blocks(self):
        value = claims()
        value["repository"] = "attacker/repo"
        with self.assertRaisesRegex(IdentityVerificationError, "repository"):
            validate_bound_claims(value, expected_sha=SHA,
                                  expected_workflow_sha=SHA, expected_run_id="12345", expected_run_attempt="1")

    def test_wrong_workflow_blocks(self):
        value = claims()
        value["workflow_ref"] = "Lornt1666/AIGC/.github/workflows/other.yml@refs/heads/main"
        with self.assertRaisesRegex(IdentityVerificationError, "workflow_ref"):
            validate_bound_claims(value, expected_sha=SHA,
                                  expected_workflow_sha=SHA, expected_run_id="12345", expected_run_attempt="1")

    def test_wrong_revision_blocks(self):
        value = claims()
        value["sha"] = "b" * 40
        with self.assertRaisesRegex(IdentityVerificationError, "sha"):
            validate_bound_claims(value, expected_sha=SHA,
                                  expected_workflow_sha=SHA, expected_run_id="12345", expected_run_attempt="1")

    def test_pull_request_event_blocks(self):
        value = claims()
        value["event_name"] = "pull_request"
        with self.assertRaisesRegex(IdentityVerificationError, "event_name"):
            validate_bound_claims(value, expected_sha=SHA,
                                  expected_workflow_sha=SHA, expected_run_id="12345", expected_run_attempt="1")


if __name__ == "__main__":
    unittest.main()
