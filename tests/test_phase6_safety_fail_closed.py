from __future__ import annotations

from datetime import datetime, timedelta, timezone
import hashlib

from src.phase6_controlled_execution import (
    ExecutionSafety,
    Phase6Validator,
    build_packet_from_phase5_authorization,
)


def _sha256(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _authorization_packet(artifact: str) -> dict:
    return {
        "authorization_id": "AUTH-TEST-001",
        "action_id": "ACTION-TEST-001",
        "proposal_id": "PROPOSAL-TEST-001",
        "opportunity_id": "OPPORTUNITY-TEST-001",
        "operator": "test-operator",
        "decision": "approved_for_phase_6",
        "expires_at": (datetime.now(timezone.utc) + timedelta(minutes=5)).isoformat(),
        "recipient": "recipient@example.invalid",
        "platform": "test-platform",
        "source_url": "https://example.invalid/opportunity",
        "proposed_external_action": "send proposal",
        "artifact": {
            "artifact_type": "proposal",
            "artifact_hash": _sha256(artifact),
            "artifact_preview": artifact,
        },
        "phase6_status": {
            "authorized_for_phase6": True,
            "execution_scope": "test-only",
        },
        "approval": {"approved_at": datetime.now(timezone.utc).isoformat()},
    }


def test_packet_construction_does_not_claim_safety_controls_ran() -> None:
    artifact = "A deterministic test proposal."
    packet = build_packet_from_phase5_authorization(
        _authorization_packet(artifact),
        {"proposal_id": "PROPOSAL-TEST-001", "employer_facing_message": artifact},
    )

    assert packet.safety.platform_policy_checked is False
    assert packet.safety.ai_disclosure_preserved is False
    assert packet.safety.privacy_checked is False
    assert any("unverified" in note.lower() for note in packet.safety.notes)
    assert Phase6Validator().validate(packet) == (
        "Platform policy check was not confirmed by evidence."
    )


def test_platform_policy_gate_fails_closed_even_if_other_flags_are_true() -> None:
    artifact = "A deterministic test proposal."
    packet = build_packet_from_phase5_authorization(
        _authorization_packet(artifact),
        {"proposal_id": "PROPOSAL-TEST-001", "employer_facing_message": artifact},
    )
    packet.safety = ExecutionSafety(
        platform_policy_checked=False,
        ai_disclosure_preserved=True,
        privacy_checked=True,
    )

    assert Phase6Validator().validate(packet) == (
        "Platform policy check was not confirmed by evidence."
    )
