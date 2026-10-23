"""Ed25519 verification for signed external evidence receipts.

This verifies cryptographic signatures and explicit claims; it does not establish
that a key owner is authorized unless the caller supplies a trusted, policy-managed
key allowlist. Unknown keys, expired keys, wrong purpose, wrong bindings, malformed
signatures and replayed receipt IDs fail closed.
"""
from __future__ import annotations

from dataclasses import dataclass
import base64
import hashlib
import json
from typing import Any, Mapping

try:
    from cryptography.exceptions import InvalidSignature
    from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey
except ImportError:  # fail closed without silently accepting unsigned receipts
    InvalidSignature = Exception
    Ed25519PublicKey = None  # type: ignore[assignment]


def canonical_bytes(value: Any) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False).encode("utf-8")


@dataclass(frozen=True)
class TrustedReceiptKey:
    key_id: str
    public_key_b64: str
    issuer: str
    allowed_purposes: tuple[str, ...]
    status: str = "ACTIVE"


class ReceiptVerificationError(ValueError):
    pass


class Ed25519ReceiptVerifier:
    def __init__(self, trusted_keys: list[TrustedReceiptKey], *, revoked_receipt_ids: set[str] | None = None):
        self.keys = {key.key_id: key for key in trusted_keys}
        if len(self.keys) != len(trusted_keys):
            raise ReceiptVerificationError("duplicate_trusted_key_id")
        self.revoked = set(revoked_receipt_ids or ())

    def verify(self, envelope: Mapping[str, Any], *, expected_purpose: str,
               expected_bindings: Mapping[str, Any]) -> dict[str, Any]:
        if Ed25519PublicKey is None:
            raise ReceiptVerificationError("cryptography_dependency_unavailable")
        if not isinstance(envelope, Mapping):
            raise ReceiptVerificationError("receipt_envelope_not_object")
        payload = envelope.get("payload")
        signature_b64 = envelope.get("signature")
        key_id = envelope.get("key_id")
        if not isinstance(payload, Mapping) or not isinstance(signature_b64, str) or not isinstance(key_id, str):
            raise ReceiptVerificationError("receipt_envelope_malformed")
        key = self.keys.get(key_id)
        if key is None or key.status != "ACTIVE":
            raise ReceiptVerificationError("receipt_signing_key_untrusted_or_inactive")
        if payload.get("issuer") != key.issuer:
            raise ReceiptVerificationError("receipt_issuer_mismatch")
        if payload.get("purpose") != expected_purpose or expected_purpose not in key.allowed_purposes:
            raise ReceiptVerificationError("receipt_purpose_not_authorized")
        receipt_id = payload.get("receipt_id")
        if not isinstance(receipt_id, str) or not receipt_id:
            raise ReceiptVerificationError("receipt_id_missing")
        if receipt_id in self.revoked:
            raise ReceiptVerificationError("receipt_revoked_or_replayed")
        for name, expected in expected_bindings.items():
            if payload.get(name) != expected:
                raise ReceiptVerificationError("receipt_binding_mismatch:" + str(name))
        if not isinstance(payload.get("issued_at"), str) or not isinstance(payload.get("expires_at"), str):
            raise ReceiptVerificationError("receipt_validity_window_missing")
        # Strict UTC timestamps and current validity; no naive local-time interpretation.
        from datetime import datetime, timezone
        try:
            issued = datetime.fromisoformat(payload["issued_at"].replace("Z", "+00:00"))
            expires = datetime.fromisoformat(payload["expires_at"].replace("Z", "+00:00"))
        except ValueError as exc:
            raise ReceiptVerificationError("receipt_validity_window_malformed") from exc
        now = datetime.now(timezone.utc)
        if issued.tzinfo is None or expires.tzinfo is None or issued > now or expires <= now or expires <= issued:
            raise ReceiptVerificationError("receipt_outside_validity_window")
        try:
            public_raw = base64.b64decode(key.public_key_b64, validate=True)
            signature = base64.b64decode(signature_b64, validate=True)
            if len(public_raw) != 32 or len(signature) != 64:
                raise ReceiptVerificationError("ed25519_key_or_signature_length_invalid")
            Ed25519PublicKey.from_public_bytes(public_raw).verify(signature, canonical_bytes(payload))
        except ReceiptVerificationError:
            raise
        except (ValueError, InvalidSignature) as exc:
            raise ReceiptVerificationError("receipt_signature_invalid") from exc
        digest = "sha256:" + hashlib.sha256(canonical_bytes(payload)).hexdigest()
        return {"verified": True, "receipt_id": receipt_id, "issuer": key.issuer,
                "key_id": key_id, "purpose": expected_purpose, "payload_digest": digest,
                "bindings": dict(expected_bindings), "verification_method": "Ed25519",
                "authorization_note": "signature valid under caller-supplied trusted-key policy; key authorization is external policy input"}
