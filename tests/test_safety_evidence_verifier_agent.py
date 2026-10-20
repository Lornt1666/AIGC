from datetime import datetime, timedelta, timezone
import json
from pathlib import Path

from src.phase6_controlled_execution import (
    ExecutionArtifact, ExecutionAuthorization, ExecutionMode, ExecutionPacket,
    ExecutionSafety, HashTools,
)
from src.safety_evidence_verifier import SafetyEvidenceVerifier, REQUIRED_CHECKS
from src.safety_evidence_verifier_agent import SafetyEvidenceVerifierAgent


NOW = datetime.now(timezone.utc)
SECRETS = {
    "policy-checker": "test-policy-secret-that-is-at-least-32-bytes",
    "disclosure-checker": "test-disclosure-secret-at-least-32-bytes",
    "privacy-checker": "test-privacy-secret-that-is-at-least-32-bytes",
}
ISSUERS = {
    "platform_policy": "policy-checker",
    "ai_disclosure": "disclosure-checker",
    "privacy": "privacy-checker",
}


def packet():
    content = "approved artifact"
    digest = HashTools.hash_text(content)
    auth = ExecutionAuthorization(
        approved_for_phase6=True,
        authorization_id="auth-1",
        action_id="action-1",
        proposal_id="proposal-1",
        opportunity_id="opportunity-1",
        operator="reviewer",
        approved_at=(NOW - timedelta(minutes=1)).isoformat(),
        expires_at=(NOW + timedelta(minutes=30)).isoformat(),
        artifact_hash_at_approval=digest,
        execution_scope="submit this exact proposal",
        recipient="recipient@example.invalid",
        platform="example.invalid",
        source_url="https://example.invalid/opportunity/1",
    )
    result = ExecutionPacket(
        authorization=auth,
        artifact=ExecutionArtifact("proposal", content, digest),
        action_type="send_proposal",
        execution_mode=ExecutionMode.MANUAL_HANDOFF.value,
        safety=ExecutionSafety(),
    )
    records = []
    for index, check in enumerate(sorted(REQUIRED_CHECKS)):
        payload = {
            "evidence_id": f"evidence-{index}",
            "issuer_id": ISSUERS[check],
            "check_id": check,
            "result": True,
            "issued_at": (NOW - timedelta(minutes=1)).isoformat(),
            "expires_at": (NOW + timedelta(minutes=10)).isoformat(),
            "policy_version": "policy-2026-10",
            "verifier_version": "test-verifier-1",
            "authorization_id": auth.authorization_id,
            "action_id": auth.action_id,
            "proposal_id": auth.proposal_id,
            "artifact_sha256": digest,
            "recipient": auth.recipient,
            "platform": auth.platform,
            "scope": auth.execution_scope,
        }
        records.append({
            "payload": payload,
            "signature": SafetyEvidenceVerifier.sign_for_trusted_issuer(
                payload, SECRETS[ISSUERS[check]]
            ),
        })
    result.safety.evidence_records = records
    return result


def verifier():
    return SafetyEvidenceVerifier(
        SECRETS,
        required_policy_version="policy-2026-10",
        required_issuers_by_check=ISSUERS,
        now=lambda: NOW,
    )


def test_agent_emits_durable_pass_receipt_bound_to_exact_packet(tmp_path: Path):
    receipt_path = tmp_path / "audit" / "receipts.jsonl"
    agent = SafetyEvidenceVerifierAgent(verifier(), tmp_path, receipt_path)

    receipt = agent.run(packet())

    assert receipt.verdict == "PASS"
    assert receipt.packet_sha256
    assert receipt.evidence_manifest_sha256
    assert receipt.receipt_sha256
    assert receipt.authorization_id == "auth-1"
    persisted = json.loads(receipt_path.read_text(encoding="utf-8").splitlines()[0])
    assert persisted["receipt_sha256"] == receipt.receipt_sha256


def test_agent_emits_block_receipt_for_missing_evidence(tmp_path: Path):
    item = packet()
    item.safety.evidence_records = []
    receipt_path = tmp_path / "audit" / "receipts.jsonl"
    agent = SafetyEvidenceVerifierAgent(verifier(), tmp_path, receipt_path)

    receipt = agent.run(item)

    assert receipt.verdict == "BLOCK"
    assert "missing" in receipt.reason.lower()
    assert receipt_path.exists()
