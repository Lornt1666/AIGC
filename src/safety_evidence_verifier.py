"""Fail-closed verification of signed, action-bound Phase 6 safety evidence.

Evidence issuers must be provisioned out-of-band. This module never issues safety
evidence and never treats model output or packet booleans as proof.
"""
from __future__ import annotations

import hashlib
import hmac
import json
import os
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, Iterable, Mapping, Optional


REQUIRED_CHECKS = frozenset({
    "platform_policy",
    "ai_disclosure",
    "privacy",
})
MAX_EVIDENCE_LIFETIME = timedelta(hours=24)
MAX_FUTURE_SKEW = timedelta(seconds=30)


def canonical_json(value: Any) -> bytes:
    return json.dumps(
        value, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    ).encode("utf-8")


def parse_utc(value: Any) -> Optional[datetime]:
    if not isinstance(value, str) or not value:
        return None
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None:
        return None
    return parsed.astimezone(timezone.utc)


class SafetyEvidenceVerifier:
    """Verify HMAC-signed claims from explicitly trusted evidence issuers.

    Keys are shared secrets provisioned to trusted checkers and the verifier by an
    operator outside the model/runtime. Never store keys in source control or task
    payloads. HMAC is suitable only when issuer and verifier can protect a shared
    secret; deployments requiring separation of duties should use a KMS-backed
    asymmetric signature adapter.
    """

    def __init__(self, trusted_issuer_keys: Mapping[str, str], *, now=None):
        self._keys = {
            issuer: key.encode("utf-8")
            for issuer, key in trusted_issuer_keys.items()
            if isinstance(issuer, str) and issuer.strip()
            and isinstance(key, str) and len(key.encode("utf-8")) >= 32
        }
        self._now = now or (lambda: datetime.now(timezone.utc))

    @classmethod
    def from_environment(cls) -> "SafetyEvidenceVerifier":
        raw = os.environ.get("AIGC_SAFETY_EVIDENCE_HMAC_KEYS_JSON", "")
        if not raw:
            return cls({})
        try:
            value = json.loads(raw)
        except json.JSONDecodeError:
            return cls({})
        if not isinstance(value, dict):
            return cls({})
        return cls(value)

    @staticmethod
    def sign_for_trusted_issuer(payload: Dict[str, Any], secret: str) -> str:
        """Signing helper for trusted adapter implementations and tests only."""
        if not isinstance(secret, str) or len(secret.encode("utf-8")) < 32:
            raise ValueError("Evidence signing key must contain at least 32 bytes.")
        return hmac.new(secret.encode("utf-8"), canonical_json(payload), hashlib.sha256).hexdigest()

    def verify(self, packet: Any, evidence_records: Iterable[Dict[str, Any]]) -> Optional[str]:
        if not self._keys:
            return "Safety evidence trust configuration is missing or invalid."
        if not isinstance(evidence_records, (list, tuple)):
            return "Safety evidence records must be a list."
        auth = packet.authorization
        expected = {
            "authorization_id": auth.authorization_id,
            "action_id": auth.action_id,
            "proposal_id": auth.proposal_id,
            "artifact_sha256": packet.artifact.hash,
            "recipient": auth.recipient,
            "platform": auth.platform,
            "scope": auth.execution_scope,
        }
        now = self._now().astimezone(timezone.utc)
        verified_checks = set()
        seen_ids = set()

        for record in evidence_records:
            if not isinstance(record, dict):
                return "Safety evidence record is malformed."
            payload = record.get("payload")
            signature = record.get("signature")
            if not isinstance(payload, dict) or not isinstance(signature, str):
                return "Safety evidence payload or signature is missing."
            issuer = payload.get("issuer_id")
            secret = self._keys.get(issuer) if isinstance(issuer, str) else None
            if secret is None:
                return "Safety evidence issuer is not trusted."
            expected_signature = hmac.new(secret, canonical_json(payload), hashlib.sha256).hexdigest()
            if not hmac.compare_digest(signature, expected_signature):
                return "Safety evidence signature is invalid."
            evidence_id = payload.get("evidence_id")
            if not isinstance(evidence_id, str) or not evidence_id or evidence_id in seen_ids:
                return "Safety evidence identifier is missing or duplicated."
            seen_ids.add(evidence_id)
            check_id = payload.get("check_id")
            if check_id not in REQUIRED_CHECKS:
                return "Safety evidence check type is not required or recognized."
            if payload.get("result") is not True:
                return f"Safety evidence check did not pass: {check_id}."
            if payload.get("policy_version") in (None, "") or payload.get("verifier_version") in (None, ""):
                return "Safety evidence is missing policy or verifier version."
            for field, value in expected.items():
                if payload.get(field) != value:
                    return f"Safety evidence binding mismatch: {field}."
            issued_at = parse_utc(payload.get("issued_at"))
            expires_at = parse_utc(payload.get("expires_at"))
            if issued_at is None or expires_at is None:
                return "Safety evidence timestamps must include a timezone."
            if issued_at > now + MAX_FUTURE_SKEW:
                return "Safety evidence was issued in the future."
            if expires_at <= now:
                return "Safety evidence has expired."
            if expires_at <= issued_at or expires_at - issued_at > MAX_EVIDENCE_LIFETIME:
                return "Safety evidence validity window is invalid."
            verified_checks.add(check_id)

        missing = REQUIRED_CHECKS - verified_checks
        if missing:
            return "Required signed safety evidence is missing: " + ", ".join(sorted(missing)) + "."
        return None
