from __future__ import annotations

import hashlib
import json
import uuid
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from typing import Any, Dict, List


NIST_PQC_STANDARDS = [
    "FIPS 203 ML-KEM",
    "FIPS 204 ML-DSA",
    "FIPS 205 SLH-DSA",
]


@dataclass(frozen=True)
class OnionLayer:
    layer_id: str
    name: str
    purpose: str
    algorithm_or_control: str
    status: str
    protects_against: List[str]
    secret_material_included: bool = False
    external_action_performed: bool = False


def build_post_quantum_onion_envelope(
    artifact_id: str,
    payload: Dict[str, Any],
    purpose: str = "governed_artifact_protection",
    key_reference: str = "env:AIGC_POST_QUANTUM_ONION_KEY_REFERENCE",
) -> Dict[str, Any]:
    canonical = canonical_json(payload)
    digest = hashlib.sha3_256(canonical.encode("utf-8")).hexdigest()
    envelope_id = "AIGC-PQ-ONION-" + hashlib.sha256(f"{artifact_id}:{digest}".encode("utf-8")).hexdigest()[:16].upper()
    envelope = {
        "envelope_id": envelope_id,
        "created_at": utc_now(),
        "artifact_id": artifact_id,
        "purpose": purpose,
        "payload_digest_sha3_256": digest,
        "payload_included": False,
        "payload_bytes_included": 0,
        "layer_count": len(default_onion_layers()),
        "layers": [asdict(layer) for layer in default_onion_layers()],
        "post_quantum_readiness": {
            "standards_referenced": NIST_PQC_STANDARDS,
            "implemented_now": [
                "canonical_payload_digest",
                "layer_manifest",
                "secret_reference_boundary",
                "audit_hash_ready_identifier",
            ],
            "requires_external_crypto_provider": True,
            "migration_note": "Use vetted cryptographic libraries or managed KMS/HSM services for real encryption and post-quantum key establishment.",
        },
        "key_reference": key_reference,
        "secret_material_included": False,
        "cryptographic_claims": {
            "literal_quantum_encryption_claim": False,
            "real_encryption_performed": False,
            "qkd_claim": False,
            "safe_description": "post_quantum_ready_onion_envelope_plan",
        },
        "approval_boundary": {
            "human_review_required_before_external_exchange": True,
            "self_approval_allowed": False,
            "external_action_default": False,
        },
        "external_action_performed": False,
    }
    return validate_post_quantum_onion_envelope(envelope)


def default_onion_layers() -> List[OnionLayer]:
    return [
        OnionLayer(
            layer_id="layer_01_canonicalization",
            name="Canonical payload digest",
            purpose="Bind the artifact to a stable JSON representation without storing the payload in the envelope.",
            algorithm_or_control="canonical_json + SHA3-256",
            status="implemented_metadata_control",
            protects_against=["artifact_mutation_after_review", "ambiguous_serialization"],
        ),
        OnionLayer(
            layer_id="layer_02_symmetric_content_encryption",
            name="Symmetric content encryption boundary",
            purpose="Reserve a vetted AEAD content-encryption layer for deployment-time payload protection.",
            algorithm_or_control="AES-256-GCM or ChaCha20-Poly1305 through vetted provider",
            status="provider_required_not_implemented_here",
            protects_against=["passive_payload_disclosure", "tampering_without_auth_tag"],
        ),
        OnionLayer(
            layer_id="layer_03_secret_manager_key_boundary",
            name="Secret manager key isolation",
            purpose="Keep key material outside Git and outside logs through environment or managed secret references.",
            algorithm_or_control="external KMS/HSM/secret-manager reference",
            status="reference_only",
            protects_against=["secret_logging", "credential_commit", "operator_token_leakage"],
        ),
        OnionLayer(
            layer_id="layer_04_post_quantum_kem",
            name="Post-quantum key establishment readiness",
            purpose="Reserve a post-quantum key encapsulation layer for approved live integrations.",
            algorithm_or_control="NIST FIPS 203 ML-KEM",
            status="migration_target_external_provider_required",
            protects_against=["future_quantum_key_recovery_risk"],
        ),
        OnionLayer(
            layer_id="layer_05_post_quantum_signature",
            name="Post-quantum signature readiness",
            purpose="Reserve a post-quantum signing layer for release archives, permit packets, and handoff receipts.",
            algorithm_or_control="NIST FIPS 204 ML-DSA or FIPS 205 SLH-DSA",
            status="migration_target_external_provider_required",
            protects_against=["artifact_forgery", "release_provenance_tampering"],
        ),
        OnionLayer(
            layer_id="layer_06_audit_hash_chain",
            name="Audit hash-chain linkage",
            purpose="Link envelopes, approvals, results, and receipts without exposing secrets.",
            algorithm_or_control="SHA3-256 chained audit digest",
            status="implemented_metadata_control",
            protects_against=["undetected_history_rewrite", "missing_audit_context"],
        ),
        OnionLayer(
            layer_id="layer_07_human_approval_gate",
            name="Human approval gate",
            purpose="Prevent encrypted packaging from becoming unchecked external action.",
            algorithm_or_control="exact_scope_human_review_required",
            status="policy_control",
            protects_against=["self_approval", "unchecked_outward_action", "automatic_delivery"],
        ),
    ]


def validate_post_quantum_onion_envelope(envelope: Dict[str, Any]) -> Dict[str, Any]:
    if envelope.get("secret_material_included") is not False:
        raise ValueError("Post-quantum onion envelope must not include secret material.")
    if envelope.get("external_action_performed") is not False:
        raise ValueError("Post-quantum onion envelope must not perform external action.")
    claims = envelope.get("cryptographic_claims", {})
    if claims.get("literal_quantum_encryption_claim") is not False:
        raise ValueError("Do not claim literal quantum encryption.")
    if claims.get("qkd_claim") is not False:
        raise ValueError("Do not claim QKD without dedicated quantum-key-distribution infrastructure.")
    if claims.get("real_encryption_performed") is not False:
        raise ValueError("This envelope is a metadata and readiness layer, not an encryption implementation.")
    if envelope.get("payload_included") is not False or envelope.get("payload_bytes_included") != 0:
        raise ValueError("Payload bytes must not be included in the planning envelope.")
    layers = envelope.get("layers", [])
    if len(layers) < 5:
        raise ValueError("Post-quantum onion envelope requires layered controls.")
    for layer in layers:
        if layer.get("secret_material_included") is not False:
            raise ValueError(f"{layer.get('layer_id')} must not include secret material.")
        if layer.get("external_action_performed") is not False:
            raise ValueError(f"{layer.get('layer_id')} must not perform external action.")
    return envelope


def canonical_json(payload: Dict[str, Any]) -> str:
    return json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def make_envelope_audit_event(envelope: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "event_id": str(uuid.uuid4()),
        "timestamp": utc_now(),
        "event_type": "post_quantum_onion_envelope_planned",
        "envelope_id": envelope.get("envelope_id", ""),
        "artifact_id": envelope.get("artifact_id", ""),
        "payload_digest_sha3_256": envelope.get("payload_digest_sha3_256", ""),
        "secret_material_included": False,
        "external_action_performed": False,
    }


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()
