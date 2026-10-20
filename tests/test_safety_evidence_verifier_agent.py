from datetime import datetime, timedelta, timezone
import json
import subprocess
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


def git_project(path: Path) -> Path:
    path.mkdir(parents=True, exist_ok=True)
    subprocess.run(["git", "init", str(path)], check=True, capture_output=True)
    subprocess.run(["git", "-C", str(path), "config", "user.email", "test@example.invalid"], check=True)
    subprocess.run(["git", "-C", str(path), "config", "user.name", "AIGC Test"], check=True)
    (path / "tracked.txt").write_text("test fixture\\n", encoding="utf-8")
    subprocess.run(["git", "-C", str(path), "add", "tracked.txt"], check=True)
    subprocess.run(["git", "-C", str(path), "commit", "-m", "test fixture"], check=True, capture_output=True)
    return path


def test_agent_emits_durable_pass_receipt_bound_to_exact_packet(tmp_path: Path):
    project = git_project(tmp_path / "project")
    receipt_path = tmp_path / "receipts.jsonl"
    agent = SafetyEvidenceVerifierAgent(verifier(), project, receipt_path)

    receipt = agent.run(packet())

    assert receipt.verdict == "PASS"
    assert receipt.packet_sha256
    assert receipt.evidence_manifest_sha256
    assert receipt.receipt_sha256
    assert receipt.authorization_id == "auth-1"
    second_receipt = agent.run(packet())
    assert second_receipt.verdict == "PASS"
    lines = receipt_path.read_text(encoding="utf-8").splitlines()
    assert len(lines) == 2, "each appended receipt must occupy one JSONL line"
    persisted = [json.loads(line) for line in lines]
    assert persisted[0]["receipt_sha256"] == receipt.receipt_sha256
    assert persisted[1]["receipt_sha256"] == second_receipt.receipt_sha256


def test_agent_emits_block_receipt_for_missing_evidence(tmp_path: Path):
    project = git_project(tmp_path / "project")
    item = packet()
    item.safety.evidence_records = []
    receipt_path = tmp_path / "receipts.jsonl"
    agent = SafetyEvidenceVerifierAgent(verifier(), project, receipt_path)

    receipt = agent.run(item)

    assert receipt.verdict == "BLOCK"
    assert "missing" in receipt.reason.lower()
    assert receipt_path.exists()
