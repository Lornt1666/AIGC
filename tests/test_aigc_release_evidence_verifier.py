import unittest
from copy import deepcopy

from aigc_release_evidence_verifier import VerifierPolicy, evaluate_evidence, handoff_payload, READY, BLOCK

SHA = "a" * 40
TREE = "b" * 40
D = "c" * 64
POLICY_DIGEST = "d" * 64


def policy():
    return VerifierPolicy(
        policy_id="AIGC-REL-001", policy_version="1.0.0", policy_digest=POLICY_DIGEST,
        repository="Lornt1666/AIGC", repository_id="1287333065", owner_id="1",
        workflow_path=".github/workflows/aigc-ci.yml",
        allowed_events=frozenset({"push"}), allowed_refs=frozenset({"refs/heads/main"}),
        required_checks=frozenset({"validate", "attest"}),
        required_adversarial_cases=frozenset({"wrong-sha", "bad-signature", "replay", "unknown-outcome"}),
        attestation_predicate="https://slsa.dev/provenance/v1",
        attestation_verifier="gh-attestation-verify", attestation_verifier_version="2.102.1",
    )


def receipt(evidence_type, **extra):
    value = {
        "evidence_type": evidence_type, "repository": "Lornt1666/AIGC", "repository_id": "1287333065",
        "subject_sha": SHA, "subject_tree_sha": TREE, "policy_id": "AIGC-REL-001",
        "policy_version": "1.0.0", "policy_digest": POLICY_DIGEST,
        "authenticated": True, "revoked": False, "content_sha256": D,
        "evidence_uri": "evidence://aigc/test-record", "producer_identity": "trusted-service:aigc-test",
        "verification_method": "verified-test-adapter/1.0", "verified_at": 1792600000,
    }
    value.update(extra)
    return value


def bundle():
    return {
        "subject": {
            "repository": "Lornt1666/AIGC", "repository_id": "1287333065", "commit_sha": SHA,
            "tree_sha": TREE, "ref": "refs/heads/main", "event": "push",
            "source_tree_verified": True, "author_identity": "developer:author",
            "implementer_identity": "developer:implementer",
        },
        "ci": {
            "repository": "Lornt1666/AIGC", "repository_id": "1287333065", "head_sha": SHA,
            "tree_sha": TREE, "workflow_path": ".github/workflows/aigc-ci.yml",
            "event": "push", "ref": "refs/heads/main", "run_id": "123456", "run_attempt": "2",
            "status": "completed", "conclusion": "success", "required_checks_complete": True,
            "checks": [
                {"name": "validate", "conclusion": "success", "required": True, "skipped": False},
                {"name": "attest", "conclusion": "success", "required": True, "skipped": False},
            ],
        },
        "artifact": {
            "repository": "Lornt1666/AIGC", "subject_sha": SHA, "subject_tree_sha": TREE,
            "run_id": "123456", "run_attempt": "2", "bytes_rehashed_locally": True,
            "sha256": D, "digest_matches_attestation": True, "safe_archive_inspection": True,
            "manifest_sha256": "e" * 64,
        },
        "oidc": receipt("oidc-verification", run_id="123456", run_attempt="2",
                        issuer="https://token.actions.githubusercontent.com", signature_verified=True,
                        audience_matches_policy=True, subject_matches_policy=True, claims_match_exact_run=True,
                        raw_token_retained=False, replay_protection_verified=True),
        "attestation": receipt("attestation-verification", run_id="123456", run_attempt="2",
                               verifier="gh-attestation-verify", verifier_version="2.102.1",
                               predicate_type="https://slsa.dev/provenance/v1", source_repository="Lornt1666/AIGC",
                               source_sha=SHA, source_tree_sha=TREE, subject_sha256=D, signature_verified=True,
                               transparency_verified=True, verifier_exit_code=0, structured_output_valid=True,
                               eligibility_checked=True, eligibility_supported=True, hash_only_fallback=False),
        "controller": receipt("controller-assurance", real_interface_verified=True,
                              server_side_authorization=True, durable_intent_before_dispatch=True,
                              idempotency_verified=True, restart_recovery_verified=True,
                              ambiguous_outcome_is_unknown=True, worker_bypass_denied=True,
                              admin_boundary_id="control-admin"),
        "audit": receipt("audit-service-assurance", real_interface_verified=True,
                         independent_admin_boundary=True, append_only_verified=True, tamper_detection_verified=True,
                         retention_verified=True, restore_test_passed=True, authenticated_receipts_verified=True,
                         admin_boundary_id="audit-admin"),
        "adversarial": {"real_interfaces": True, "subject_sha": SHA, "subject_tree_sha": TREE, "cases": [
            {"case_id": name, "executed": True, "expected_outcome": "DENY", "actual_outcome": "DENY",
             "evidence_digest": D}
            for name in ("wrong-sha", "bad-signature", "replay", "unknown-outcome")
        ]},
        "independent_review": receipt("independent-security-review", reviewer_authenticated=True,
                                      reviewer_independent=True, reviewer_signature_verified=True,
                                      findings_closed=True, remediation_retested=True, review_bound_to_manifest=True,
                                      reviewer_identity="reviewer:independent", evidence_manifest_sha256="e" * 64),
        "human_acceptance": receipt("human-acceptance", approver_authenticated=True, approver_authorized=True,
                                    acceptance_signature_verified=True, approval_current=True, bound_to_manifest=True,
                                    bound_to_review=True, approver_identity="approver:independent",
                                    evidence_manifest_sha256="e" * 64,
                                    review_content_sha256=D),
    }


class EvidenceVerifierTests(unittest.TestCase):
    def test_complete_packet_is_only_ready_for_canonical_review(self):
        result = evaluate_evidence(policy(), bundle())
        self.assertEqual(result["disposition"], READY)
        self.assertEqual(result["release_decision"], BLOCK)
        self.assertFalse(result["automatic_mutations_performed"])
        self.assertFalse(result["raw_tokens_emitted"])

    def test_missing_evidence_blocks(self):
        value = bundle()
        value.pop("attestation")
        result = evaluate_evidence(policy(), value)
        self.assertEqual(result["disposition"], BLOCK)
        self.assertIn("attestation_missing", result["reasons"])

    def test_wrong_commit_blocks(self):
        value = bundle()
        value["ci"]["head_sha"] = "f" * 40
        result = evaluate_evidence(policy(), value)
        self.assertEqual(result["disposition"], BLOCK)
        self.assertIn("ci_head_sha_mismatch", result["reasons"])

    def test_skipped_required_check_blocks(self):
        value = bundle()
        value["ci"]["checks"][0]["skipped"] = True
        result = evaluate_evidence(policy(), value)
        self.assertEqual(result["disposition"], BLOCK)
        self.assertTrue(any("skipped" in reason for reason in result["reasons"]))

    def test_wrong_attestation_digest_blocks(self):
        value = bundle()
        value["attestation"]["subject_sha256"] = "f" * 64
        result = evaluate_evidence(policy(), value)
        self.assertEqual(result["disposition"], BLOCK)
        self.assertIn("attestation_subject_digest_mismatch", result["reasons"])

    def test_hash_only_fallback_blocks(self):
        value = bundle()
        value["attestation"]["hash_only_fallback"] = True
        result = evaluate_evidence(policy(), value)
        self.assertIn("attestation_hash_only_fallback_detected_or_unknown", result["reasons"])

    def test_same_audit_and_controller_admin_boundary_blocks(self):
        value = bundle()
        value["audit"]["admin_boundary_id"] = "control-admin"
        result = evaluate_evidence(policy(), value)
        self.assertIn("audit_not_independently_administered", result["reasons"])

    def test_controller_ambiguous_success_claim_blocks(self):
        value = bundle()
        value["controller"]["ambiguous_outcome_is_unknown"] = False
        result = evaluate_evidence(policy(), value)
        self.assertIn("controller_gate_failed:ambiguous_outcome_is_unknown", result["reasons"])

    def test_missing_adversarial_case_blocks(self):
        value = bundle()
        value["adversarial"]["cases"].pop()
        result = evaluate_evidence(policy(), value)
        self.assertTrue(any(reason.startswith("adversarial_case_missing") for reason in result["reasons"]))

    def test_non_independent_reviewer_blocks(self):
        value = bundle()
        value["independent_review"]["reviewer_identity"] = "developer:implementer"
        result = evaluate_evidence(policy(), value)
        self.assertIn("reviewer_not_independent_of_author_or_implementer", result["reasons"])

    def test_human_acceptance_wrong_review_binding_blocks(self):
        value = bundle()
        value["human_acceptance"]["review_content_sha256"] = "f" * 64
        result = evaluate_evidence(policy(), value)
        self.assertIn("acceptance_review_binding_mismatch", result["reasons"])

    def test_deterministic_receipt_digest(self):
        first = evaluate_evidence(policy(), bundle())
        second = evaluate_evidence(policy(), bundle())
        self.assertEqual(first, second)

    def test_handoff_is_not_release_authorization(self):
        result = evaluate_evidence(policy(), bundle())
        handoff = handoff_payload(result, evidence_manifest_uri="evidence://manifest/123",
                                  evidence_manifest_sha256="e" * 64)
        self.assertEqual(handoff["release_authorization"], "NOT_GRANTED")
        self.assertEqual(handoff["destination"], "canonical Release Assurance Agent")

    def test_blocked_receipt_cannot_be_handed_off(self):
        result = evaluate_evidence(policy(), {"subject": {}})
        with self.assertRaisesRegex(ValueError, "handoff_blocked"):
            handoff_payload(result, evidence_manifest_uri="evidence://manifest/123",
                            evidence_manifest_sha256="e" * 64)


if __name__ == "__main__":
    unittest.main()
