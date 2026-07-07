from __future__ import annotations

import pytest

from src.core.contract_validator import validate_artifact
from src.security.post_quantum_onion import (
    NIST_PQC_STANDARDS,
    build_post_quantum_onion_envelope,
    make_envelope_audit_event,
    validate_post_quantum_onion_envelope,
)


def test_post_quantum_onion_envelope_is_valid_and_non_secret() -> None:
    payload = {"artifact_id": "AIGC-ARTIFACT-001", "status": "review_ready", "external_action_performed": False}

    envelope = build_post_quantum_onion_envelope("AIGC-ARTIFACT-001", payload)

    assert validate_artifact("post_quantum_onion_envelope", envelope) == envelope
    assert envelope["payload_included"] is False
    assert envelope["payload_bytes_included"] == 0
    assert envelope["secret_material_included"] is False
    assert envelope["external_action_performed"] is False
    assert envelope["cryptographic_claims"]["literal_quantum_encryption_claim"] is False
    assert envelope["cryptographic_claims"]["real_encryption_performed"] is False
    assert envelope["cryptographic_claims"]["qkd_claim"] is False
    assert set(NIST_PQC_STANDARDS).issubset(set(envelope["post_quantum_readiness"]["standards_referenced"]))


def test_post_quantum_onion_rejects_unsafe_crypto_claims() -> None:
    envelope = build_post_quantum_onion_envelope("AIGC-ARTIFACT-002", {"status": "review_ready"})
    envelope["cryptographic_claims"]["literal_quantum_encryption_claim"] = True

    with pytest.raises(ValueError, match="literal quantum encryption"):
        validate_post_quantum_onion_envelope(envelope)


def test_post_quantum_onion_rejects_secret_material_and_payload_bytes() -> None:
    envelope = build_post_quantum_onion_envelope("AIGC-ARTIFACT-003", {"status": "review_ready"})
    envelope["secret_material_included"] = True

    with pytest.raises(ValueError, match="secret material"):
        validate_post_quantum_onion_envelope(envelope)

    envelope = build_post_quantum_onion_envelope("AIGC-ARTIFACT-004", {"status": "review_ready"})
    envelope["payload_included"] = True
    envelope["payload_bytes_included"] = 128

    with pytest.raises(ValueError, match="Payload bytes"):
        validate_post_quantum_onion_envelope(envelope)


def test_post_quantum_onion_audit_event_has_no_external_action() -> None:
    envelope = build_post_quantum_onion_envelope("AIGC-ARTIFACT-005", {"status": "review_ready"})
    audit_event = make_envelope_audit_event(envelope)

    assert audit_event["envelope_id"] == envelope["envelope_id"]
    assert audit_event["payload_digest_sha3_256"] == envelope["payload_digest_sha3_256"]
    assert audit_event["secret_material_included"] is False
    assert audit_event["external_action_performed"] is False
