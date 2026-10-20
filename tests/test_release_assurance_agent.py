from __future__ import annotations

import hashlib
from datetime import datetime, timedelta, timezone

from src.release_assurance_agent import (
    EXPECTED_STAGES, REQUIRED_RELEASE_CHECKS, ReleaseAssuranceAgent, canonical, sha256,
)


NOW = datetime(2026, 10, 20, 12, 0, tzinfo=timezone.utc)
KEYS = {f"issuer-{i}": f"test-only-key-{i}-" + "x" * 40 for i in range(len(REQUIRED_RELEASE_CHECKS))}
ISSUER_MAP = {check: f"issuer-{i}" for i, check in enumerate(sorted(REQUIRED_RELEASE_CHECKS))}
COMMIT = "a" * 40
TREE = "b" * 40
ARTIFACT = "c" * 64


def stage(stage_id):
    record = {
        "stage_id": stage_id, "target_sha": COMMIT, "tested_tree_sha": TREE,
        "run_id": 123, "status": "success", "external_action_performed": False,
        "production_activation_authorized": False, "merge_authority_granted": False,
        "deployment_authority_granted": False, "live_model_call_authority_granted": False,
        "financial_authority_granted": False,
    }
    record["record_sha256"] = sha256(canonical(record))
    return record


def packet():
    ci = {
        "conclusion": "success", "repository": "Lornt1666/AIGC",
        "target_sha": COMMIT, "tested_tree_sha": TREE, "run_id": 123,
        "contract_id": "AIGC-CI-EXACT-SHA-V1", "contract_sha256": "d" * 64,
        "workflow_revision": "e" * 40, "expected_workflow_revision": "e" * 40,
        "stage_receipts": [stage(item) for item in EXPECTED_STAGES],
    }
    result = {
        "subject": {"commit_sha": COMMIT, "tree_sha": TREE, "artifact_sha256": ARTIFACT},
        "canonical_ci": ci, "release_tier": "production", "release_attestations": [],
    }
    for check, issuer in ISSUER_MAP.items():
        payload = {
            "issuer_id": issuer, "evidence_id": f"evidence-{check}", "check_id": check,
            "result": True, "policy_version": "policy-2026.10",
            "commit_sha": COMMIT, "tree_sha": TREE, "artifact_sha256": ARTIFACT,
            "release_tier": "production", "checker_version": f"{check}/1.0",
            "issued_at": NOW.isoformat(), "expires_at": (NOW + timedelta(hours=1)).isoformat(),
        }
        result["release_attestations"].append({
            "payload": payload,
            "signature": ReleaseAssuranceAgent.sign_for_trusted_issuer(payload, KEYS[issuer]),
        })
    return result


def agent():
    return ReleaseAssuranceAgent(
        KEYS, "policy-2026.10", ISSUER_MAP, now=lambda: NOW,
        provenance_verifier=lambda ci, subject: True,
    )


def test_complete_exact_head_evidence_approves_but_does_not_deploy():
    decision = agent().evaluate(packet())
    assert decision["verdict"] == "APPROVE"
    assert decision["deployment_performed"] is False
    assert decision["merge_performed"] is False


def test_missing_canonical_stage_blocks():
    value = packet()
    value["canonical_ci"]["stage_receipts"].pop()
    decision = agent().evaluate(value)
    assert decision["verdict"] == "BLOCK"
    assert any("stage set mismatch" in reason for reason in decision["reasons"])


def test_stage_receipt_tampering_blocks():
    value = packet()
    value["canonical_ci"]["stage_receipts"][0]["status"] = "failure"
    decision = agent().evaluate(value)
    assert decision["verdict"] == "BLOCK"


def test_wrong_commit_and_tree_blocks():
    value = packet()
    value["canonical_ci"]["target_sha"] = "f" * 40
    decision = agent().evaluate(value)
    assert decision["verdict"] == "BLOCK"


def test_missing_trusted_checker_evidence_blocks():
    value = packet()
    value["release_attestations"] = value["release_attestations"][:-1]
    decision = agent().evaluate(value)
    assert decision["verdict"] == "BLOCK"
    assert any("missing" in reason for reason in decision["reasons"])


def test_bad_signature_blocks():
    value = packet()
    value["release_attestations"][0]["signature"] = "0" * 64
    assert agent().evaluate(value)["verdict"] == "BLOCK"


def test_expired_attestation_blocks():
    value = packet()
    payload = value["release_attestations"][0]["payload"]
    payload["expires_at"] = (NOW - timedelta(seconds=1)).isoformat()
    issuer = payload["issuer_id"]
    value["release_attestations"][0]["signature"] = ReleaseAssuranceAgent.sign_for_trusted_issuer(payload, KEYS[issuer])
    assert agent().evaluate(value)["verdict"] == "BLOCK"


def test_policy_and_issuer_mismatch_blocks():
    value = packet()
    payload = value["release_attestations"][0]["payload"]
    payload["policy_version"] = "stale-policy"
    issuer = payload["issuer_id"]
    value["release_attestations"][0]["signature"] = ReleaseAssuranceAgent.sign_for_trusted_issuer(payload, KEYS[issuer])
    assert agent().evaluate(value)["verdict"] == "BLOCK"


def test_missing_configuration_fails_closed():
    value = packet()
    decision = ReleaseAssuranceAgent({}, "", {}, now=lambda: NOW).evaluate(value)
    assert decision["verdict"] == "BLOCK"


def test_decision_is_bound_to_exact_subject():
    value = packet()
    decision = agent().evaluate(value)
    assert decision["commit_sha"] == COMMIT
    assert decision["tree_sha"] == TREE
    assert len(decision["decision_sha256"]) == 64



def test_missing_cryptographic_provenance_verifier_blocks():
    value = packet()
    no_provenance = ReleaseAssuranceAgent(KEYS, "policy-2026.10", ISSUER_MAP, now=lambda: NOW)
    decision = no_provenance.evaluate(value)
    assert decision["verdict"] == "BLOCK"
    assert any("provenance verifier is not configured" in reason for reason in decision["reasons"])
