from datetime import datetime, timedelta, timezone
import hashlib

from src.phase6_controlled_execution import (
    ExecutionArtifact,
    ExecutionAuthorization,
    ExecutionMode,
    ExecutionPacket,
    ExecutionSafety,
    Phase6Validator,
    build_packet_from_phase5_authorization,
)


def _approved_packet(safety: ExecutionSafety) -> ExecutionPacket:
    content = "approved artifact"
    digest = hashlib.sha256(content.encode("utf-8")).hexdigest()
    return ExecutionPacket(
        authorization=ExecutionAuthorization(
            approved_for_phase6=True,
            authorization_id="auth-1",
            action_id="action-1",
            proposal_id="proposal-1",
            opportunity_id="opportunity-1",
            operator="reviewer",
            approved_at=datetime.now(timezone.utc).isoformat(),
            expires_at=(datetime.now(timezone.utc) + timedelta(minutes=10)).isoformat(),
            artifact_hash_at_approval=digest,
            execution_scope="submit this exact proposal",
            recipient="recipient@example.invalid",
            platform="example.invalid",
            source_url="https://example.invalid/opportunity/1",
        ),
        artifact=ExecutionArtifact("proposal", content, digest),
        action_type="send_proposal",
        execution_mode=ExecutionMode.MANUAL_HANDOFF.value,
        safety=safety,
    )


def test_phase5_packet_builder_does_not_fabricate_safety_assertions():
    digest = hashlib.sha256(b"approved artifact").hexdigest()
    packet = build_packet_from_phase5_authorization(
        authorization_packet={
            "authorization_id": "auth-1",
            "action_id": "action-1",
            "proposal_id": "proposal-1",
            "opportunity_id": "opportunity-1",
            "decision": "approved_for_phase_6",
            "recipient": "recipient@example.invalid",
            "platform": "example.invalid",
            "expires_at": (datetime.now(timezone.utc) + timedelta(minutes=10)).isoformat(),
            "artifact": {
                "artifact_type": "proposal",
                "artifact_preview": "approved artifact",
                "artifact_hash": digest,
            },
            "phase6_status": {
                "authorized_for_phase6": True,
                "execution_scope": "submit this exact proposal",
            },
        },
        phase4_proposal={},
        execution_mode=ExecutionMode.MANUAL_HANDOFF.value,
    )

    assert packet.safety.platform_policy_checked is False
    assert packet.safety.ai_disclosure_preserved is False
    assert packet.safety.privacy_checked is False


def test_validator_blocks_when_platform_policy_evidence_is_missing():
    safety = ExecutionSafety(
        platform_policy_checked=True,
        ai_disclosure_preserved=True,
        privacy_checked=True,
    )

    error = Phase6Validator().validate(_approved_packet(safety))

    assert error == "Safety evidence trust configuration is missing or invalid."


def test_validator_blocks_when_disclosure_or_privacy_evidence_is_missing():
    validator = Phase6Validator()

    disclosure_error = validator.validate(
        _approved_packet(
            ExecutionSafety(
                platform_policy_checked=True,
                ai_disclosure_preserved=True,
                privacy_checked=True,
            )
        )
    )
    privacy_error = validator.validate(
        _approved_packet(
            ExecutionSafety(
                platform_policy_checked=True,
                ai_disclosure_preserved=True,
                privacy_checked=True,
            )
        )
    )

    # Legacy booleans do not satisfy the evidence requirement.
    assert disclosure_error == "Safety evidence trust configuration is missing or invalid."
    assert privacy_error == "Safety evidence trust configuration is missing or invalid."
