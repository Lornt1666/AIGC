import hashlib
import io
import json
import unittest
import zipfile

from aigc_required_acceptance_gate_agent import CORE_STEPS, RequiredAcceptanceGateAgent

SHA = "a" * 40
TREE = "b" * 40
RUN = 42


def evidence_zip(status="success"):
    receipt = {
        "requested_head_sha": SHA, "observed_head_sha": SHA,
        "requested_revision": SHA, "workflow_revision": SHA,
        "tested_tree_sha": TREE, "workflow_run_id": RUN,
        "repository": "Lornt1666/AIGC",
    }
    stage = {"stage_id": "unit", "target_sha": SHA, "tested_tree_sha": TREE,
             "run_id": RUN, "status": status}
    out = io.BytesIO()
    with zipfile.ZipFile(out, "w") as z:
        z.writestr("exact_head_admission_receipt.json", json.dumps(receipt))
        z.writestr("unit.json", json.dumps(stage))
    return out.getvalue()


class FakeClient:
    def __init__(self, conclusion="success", stage_status="success"):
        self.data = evidence_zip(stage_status)
        self.run = {"id": RUN, "head_sha": SHA, "head_commit": {"tree_id": TREE},
                    "status": "completed", "conclusion": conclusion}
        self.steps = [{"name": name, "status": "completed", "conclusion": "success"}
                      for name in sorted(CORE_STEPS)]
        self.jobs = [{"id": 7, "name": "validate", "status": "completed",
                      "conclusion": conclusion, "steps": self.steps}]
        self.artifacts = [{
            "id": 99, "name": "evidence-" + SHA, "expired": False,
            "digest": "sha256:" + hashlib.sha256(self.data).hexdigest(),
            "workflow_run": {"id": RUN, "head_sha": SHA},
        }]

    def get_run(self, repository, run_id):
        return self.run

    def get_jobs(self, repository, run_id):
        return self.jobs

    def get_artifacts(self, repository, run_id):
        return self.artifacts

    def download_artifact(self, repository, artifact_id):
        return self.data

    def get_job_logs(self, repository, job_id):
        return "validation failed"


class FakeAuthenticator:
    def verify(self, review, *, expected_sha, artifact_digest):
        if review != {"valid": True}:
            raise ValueError("review invalid")
        return {"authenticated": True, "approved": True,
                "subject_sha": expected_sha, "artifact_digest": artifact_digest}


class FakeHumanAcceptanceAuthenticator:
    def verify(self, acceptance, *, expected_sha, artifact_digest):
        if (acceptance.get("valid") is not True
                or acceptance.get("subject_sha") != expected_sha
                or acceptance.get("artifact_digest") != artifact_digest):
            raise ValueError("human acceptance signature invalid")
        return {"authenticated": True, "accepted": True, "subject_sha": expected_sha,
                "artifact_digest": artifact_digest, "human_id": "authorized-human"}


class FakeReleaseAssurance:
    def __init__(self):
        self.called = False

    def evaluate(self, report):
        self.called = True
        return {"decision": "BLOCK", "reason": "test authority remains canonical"}


class AcceptanceGateTests(unittest.TestCase):
    def setUp(self):
        self.client = FakeClient()
        self.assurance = FakeReleaseAssurance()
        self.agent = RequiredAcceptanceGateAgent(self.client, FakeAuthenticator(), self.assurance, FakeHumanAcceptanceAuthenticator())

    def test_failed_workflow_blocks_even_with_matching_artifact(self):
        self.client.run["conclusion"] = "failure"
        self.client.jobs[0]["conclusion"] = "failure"
        report = self.agent.inspect(repository="Lornt1666/AIGC", run_id=RUN,
                                    expected_sha=SHA, expected_tree_sha=TREE)
        self.assertEqual(report["status"], "BLOCK")
        self.assertIn("full_workflow_not_successful", report["reasons"])
        self.assertFalse(report["submitted_to_release_assurance"])
        self.assertFalse(self.assurance.called)

    def test_review_and_human_acceptance_are_both_required(self):
        report = self.agent.inspect(repository="Lornt1666/AIGC", run_id=RUN,
                                    expected_sha=SHA, expected_tree_sha=TREE)
        self.assertIn("independent_review_missing", report["reasons"])
        self.assertIn("explicit_human_acceptance_missing", report["reasons"])
        self.assertFalse(self.assurance.called)

    def test_complete_packet_is_submitted_only_to_canonical_authority(self):
        report = self.agent.inspect(
            repository="Lornt1666/AIGC", run_id=RUN, expected_sha=SHA,
            expected_tree_sha=TREE, independent_review={"valid": True},
            human_acceptance={"valid": True, "subject_sha": SHA, "artifact_digest": "sha256:" + hashlib.sha256(self.client.data).hexdigest()},
        )
        self.assertEqual(report["status"], "READY_FOR_RELEASE_ASSURANCE")
        self.assertTrue(report["submitted_to_release_assurance"])
        self.assertTrue(self.assurance.called)
        self.assertEqual(report["release_decision"], "BLOCK")

    def test_stage_tree_mismatch_blocks(self):
        self.client.data = evidence_zip()
        self.client.data = self.client.data.replace(TREE.encode(), (("c" * 40).encode()))
        self.client.artifacts[0]["digest"] = "sha256:" + hashlib.sha256(self.client.data).hexdigest()
        report = self.agent.inspect(repository="Lornt1666/AIGC", run_id=RUN,
                                    expected_sha=SHA, expected_tree_sha=TREE)
        self.assertEqual(report["status"], "BLOCK")
        self.assertTrue(any("artifact_inspection_failed" in r or "receipt_binding_mismatch" in r
                            or "stage_tree_mismatch" in r for r in report["reasons"]))


if __name__ == "__main__":
    unittest.main()
