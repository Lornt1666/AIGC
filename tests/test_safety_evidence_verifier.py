from datetime import datetime, timedelta, timezone
import copy

from src.phase6_controlled_execution import (
    ExecutionArtifact,
    ExecutionAuthorization,
    ExecutionMode,
    ExecutionPacket,
    ExecutionSafety,
    Phase6Validator,
    HashTools,
)
from src.safety_evidence_verifier import SafetyEvidenceVerifier, REQUIRED_CHECKS


SECRET = "test-only-secret-that-is-at-least-32-bytes"
NOW = datetime(2026, 10, 20, 21, 30, tzinfo=timezone.utc)


def make_packet(records=None, *, verifier=None):
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
        expires_at=(NOW + timedelta(minutes=10)).isoformat(),
        artifact_hash_at_approval=digest,
        execution_scope="submit this exact proposal",
        recipient="recipient@example.invalid",
        platform="example.invalid",
        source_url="https://example.invalid/opportunity/1",
    )
    packet = ExecutionPacket(
        authorization=auth,
        artifact=ExecutionArtifact("proposal", content, digest),
        action_type="send_proposal",
        execution_mode=ExecutionMode.MANUAL_HANDOFF.value,
        safety=ExecutionSafety(
            # These booleans are intentionally true to prove they are not evidence.
            platform_policy_checked=True,
            ai_disclosure_preserved=True,
            privacy_checked=True,
            evidence_records=records or [],
        ),
    )
    return packet


def make_records(packet, *, expires_at=None):
    auth = packet.authorization
    records = []
    for index, check_id in enumerate(sorted(REQUIRED_CHECKS)):
        payload = {
            "evidence_id": f"evidence-{index}",
            "issuer_id": "policy-checker",
            "check_id": check_id,
            "result": True,
            "issued_at": (NOW - timedelta(minutes=1)).isoformat(),
            "expires_at": (expires_at or NOW + timedelta(minutes=10)).isoformat(),
            "policy_version": "policy-2026-10",
            "verifier_version": "safety-verifier-1",
            "authorization_id": auth.authorization_id,
            "action_id": auth.action_id,
            "proposal_id": auth.proposal_id,
            "artifact_sha256": packet.artifact.hash,
            "recipient": auth.recipient,
            "platform": auth.platform,
            "scope": auth.execution_scope,
        }
        records.append({
            "payload": payload,
            "signature": SafetyEvidenceVerifier.sign_for_trusted_issuer(payload, SECRET),
        })
    return records


def verifier():
    return SafetyEvidenceVerifier({"policy-checker": SECRET}, now=lambda: NOW)


def test_signed_evidence_for_all_required_checks_passes():
    packet = make_packet()
    packet.safety.evidence_records = make_records(packet)
    assert verifier().verify(packet, packet.safety.evidence_records) is None
    assert Phase6Validator(evidence_verifier=verifier()).validate(packet) is None


def test_boolean_flags_without_signed_evidence_fail_closed():
    packet = make_packet()
    error = Phase6Validator(evidence_verifier=verifier()).validate(packet)
    assert error == "Required signed safety evidence is missing: ai_disclosure, platform_policy, privacy."


def test_tampered_signature_is_rejected():
    packet = make_packet()
    packet.safety.evidence_records = make_records(packet)
    packet.safety.evidence_records[0]["payload"]["result"] = False
    error = verifier().verify(packet, packet.safety.evidence_records)
    assert error == "Safety evidence signature is invalid."


def test_expired_evidence_is_rejected():
    packet = make_packet()
    packet.safety.evidence_records = make_records(packet, expires_at=NOW - timedelta(seconds=1))
    assert verifier().verify(packet, packet.safety.evidence_records) == "Safety evidence has expired."


def test_evidence_bound_to_another_recipient_is_rejected():
    packet = make_packet()
    packet.safety.evidence_records = make_records(packet)
    payload = packet.safety.evidence_records[0]["payload"]
    payload["recipient"] = "attacker@example.invalid"
    packet.safety.evidence_records[0]["signature"] = SafetyEvidenceVerifier.sign_for_trusted_issuer(payload, SECRET)
    assert verifier().verify(packet, packet.safety.evidence_records) == "Safety evidence binding mismatch: recipient."


def test_untrusted_issuer_is_rejected():
    packet = make_packet()
    packet.safety.evidence_records = make_records(packet)
    payload = packet.safety.evidence_records[0]["payload"]
    payload["issuer_id"] = "untrusted-model"
    packet.safety.evidence_records[0]["signature"] = SafetyEvidenceVerifier.sign_for_trusted_issuer(payload, SECRET)
    assert verifier().verify(packet, packet.safety.evidence_records) == "Safety evidence issuer is not trusted."


def test_missing_trust_configuration_fails_closed():
    packet = make_packet()
    packet.safety.evidence_records = make_records(packet)
    assert SafetyEvidenceVerifier({}).verify(packet, packet.safety.evidence_records) == (
        "Safety evidence trust configuration is missing or invalid."
    )


def test_duplicate_evidence_identifiers_are_rejected():
    packet = make_packet()
    packet.safety.evidence_records = make_records(packet)
    packet.safety.evidence_records[1]["payload"]["evidence_id"] = packet.safety.evidence_records[0]["payload"]["evidence_id"]
    packet.safety.evidence_records[1]["signature"] = SafetyEvidenceVerifier.sign_for_trusted_issuer(
        packet.safety.evidence_records[1]["payload"], SECRET
    )
    assert verifier().verify(packet, packet.safety.evidence_records) == (
        "Safety evidence identifier is missing or duplicated."
    )
