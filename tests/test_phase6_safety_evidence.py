from __future__ import annotations

from src.phase6_controlled_execution import (
    ExecutionMode,
    HashTools,
    Phase6Validator,
    build_packet_from_phase5_authorization,
)


def _authorization_packet(*, safety_evidence=None):
    artifact_content = "approved proposal content"
    packet = {
        "authorization_id": "auth-1",
        "action_id": "action-1",
        "proposal_id": "proposal-1",
        "opportunity_id": "opportunity-1",
        "operator": "test-operator",
        "expires_at": "2099-01-01T00:00:00+00:00",
        "artifact": {
            "artifact_hash": HashTools.hash_text(artifact_content),
            "artifact_preview": artifact_content,
            "artifact_type": "proposal",
        },
        "phase6_status": {
            "authorized_for_phase6": True,
            "execution_scope": "test-only",
        },
        "approval": {"approved_at": "2026-01-01T00:00:00+00:00"},
        "recipient": "test-recipient",
        "platform": "test-platform",
        "source_url": "https://example.invalid/opportunity",
        "proposed_external_action": "send proposal",
    }
    if safety_evidence is not None:
        packet["safety_evidence"] = safety_evidence
    return packet


def _build_packet(*, safety_evidence=None):
    authorization = _authorization_packet(safety_evidence=safety_evidence)
    proposal = {"employer_facing_message": "approved proposal content"}
    return build_packet_from_phase5_authorization(
        authorization,
        proposal,
        execution_mode=ExecutionMode.DRY_RUN.value,
    )


def test_phase6_packet_does_not_claim_safety_checks_without_evidence():
    packet = _build_packet()

    assert packet.safety.platform_policy_checked is False
    assert packet.safety.ai_disclosure_preserved is False
    assert packet.safety.privacy_checked is False
    assert Phase6Validator().validate(packet) == "Platform policy compliance was not confirmed."


def test_phase6_packet_accepts_only_explicit_true_safety_evidence():
    packet = _build_packet(
        safety_evidence={
            "platform_policy_checked": True,
            "ai_disclosure_preserved": True,
            "privacy_checked": True,
        }
    )

    assert packet.safety.platform_policy_checked is True
    assert packet.safety.ai_disclosure_preserved is True
    assert packet.safety.privacy_checked is True
    assert Phase6Validator().validate(packet) is None


def test_phase6_safety_evidence_fails_closed_for_truthy_non_boolean_values():
    packet = _build_packet(
        safety_evidence={
            "platform_policy_checked": "yes",
            "ai_disclosure_preserved": 1,
            "privacy_checked": ["reviewed"],
        }
    )

    assert packet.safety.platform_policy_checked is False
    assert packet.safety.ai_disclosure_preserved is False
    assert packet.safety.privacy_checked is False
    assert Phase6Validator().validate(packet) == "Platform policy compliance was not confirmed."
