"""AWS KMS RSA-PSS signer and independently pinned public-key verifier.

Private keys remain non-exportable in AWS KMS. The caller must configure a
least-privilege workload identity / IAM role outside this repository. This
module never accepts or reads a private-key file.
"""
from __future__ import annotations

import base64
import hashlib
from typing import Any, Callable

Signer = Callable[[bytes], dict[str, Any]]
Verifier = Callable[[bytes, dict[str, Any]], dict[str, Any]]
METHOD = "RSASSA_PSS_SHA_256"


def make_aws_kms_signer(kms_client: Any, key_id: str, signer_identity: str) -> Signer:
    if not key_id.strip() or not signer_identity.strip():
        raise ValueError("AWS KMS key ID and signer identity are required")

    def sign(payload: bytes) -> dict[str, Any]:
        payload_digest = hashlib.sha256(payload).digest()
        result = kms_client.sign(
            KeyId=key_id,
            Message=payload_digest,
            MessageType="DIGEST",
            SigningAlgorithm=METHOD,
        )
        signature = result.get("Signature")
        if not isinstance(signature, (bytes, bytearray)) or not signature:
            raise ValueError("AWS KMS returned no signature")
        return {
            "method": METHOD,
            "signer_identity": signer_identity,
            "signature_b64": base64.b64encode(bytes(signature)).decode("ascii"),
            "kms_key_id": key_id,
        }
    return sign


def make_rsa_pss_verifier(public_key_pem: str, trusted_signer_identity: str,
                          trust_root_id: str) -> Verifier:
    if not public_key_pem.strip() or not trusted_signer_identity.strip() or not trust_root_id.strip():
        raise ValueError("pinned public key, signer identity, and trust-root ID are required")
    try:
        from cryptography.hazmat.primitives import hashes, serialization
        from cryptography.hazmat.primitives.asymmetric import padding, rsa
        from cryptography.hazmat.primitives.asymmetric.utils import Prehashed
        public_key = serialization.load_pem_public_key(public_key_pem.encode("utf-8"))
        if not isinstance(public_key, rsa.RSAPublicKey):
            raise ValueError("trusted public key must be RSA")
    except Exception as exc:
        raise ValueError("unable to load trusted RSA public key") from exc

    def verify(payload: bytes, authentication: dict[str, Any]) -> dict[str, Any]:
        if authentication.get("method") != METHOD:
            return {"verified": False, "reason": "signature_method_mismatch"}
        if authentication.get("signer_identity") != trusted_signer_identity:
            return {"verified": False, "reason": "signer_identity_mismatch"}
        if authentication.get("signed_payload_sha256") != hashlib.sha256(payload).hexdigest():
            return {"verified": False, "reason": "signed_payload_digest_mismatch"}
        try:
            signature = base64.b64decode(authentication.get("signature_b64", ""), validate=True)
            public_key.verify(
                signature,
                hashlib.sha256(payload).digest(),
                padding.PSS(mgf=padding.MGF1(hashes.SHA256()), salt_length=padding.PSS.MAX_LENGTH),
                Prehashed(hashes.SHA256()),
            )
        except Exception:
            return {"verified": False, "reason": "signature_invalid"}
        return {"verified": True, "signer_identity": trusted_signer_identity,
                "trust_root_id": trust_root_id}
    return verify


def build_aws_kms_adapters(key_id: str, signer_identity: str, trust_root_id: str,
                           public_key_pem: str, region_name: str | None = None,
                           kms_client: Any | None = None) -> tuple[Signer, Verifier]:
    """Build adapters using boto3's default credential chain or an injected test client."""
    if kms_client is None:
        try:
            import boto3
        except ImportError as exc:
            raise RuntimeError("boto3 is required for AWS KMS signing; install the approved AWS SDK dependency") from exc
        kms_client = boto3.client("kms", region_name=region_name)
    return (
        make_aws_kms_signer(kms_client, key_id, signer_identity),
        make_rsa_pss_verifier(public_key_pem, signer_identity, trust_root_id),
    )
