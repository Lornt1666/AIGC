"""Fail-closed verifier for owner approvals bound to an exact proposal and commit.

This module verifies signed approval artifacts. Production callers must supply a
durable, atomic replay ledger and must invoke verification immediately before any
protected action. This module does not itself authorize or execute external actions.
"""
from __future__ import annotations

from dataclasses import dataclass
import hashlib
import hmac
import json
import os
import re
import time
from typing import Any, Mapping, Protocol


_SHA256 = re.compile(r"^[a-f0-9]{64}$")
_COMMIT = re.compile(r"^[a-f0-9]{40}$")


class OwnerApprovalError(ValueError):
    """Approval is missing, invalid, expired, mismatched, or already consumed."""


class ApprovalReplayLedger(Protocol):
    """Durable store whose consume_once operation is atomic across all replicas."""

    def consume_once(self, *, approval_id: str, nonce: str, payload_sha256: str) -> bool:
        """Atomically mark approval_id + nonce consumed; false means replay/conflict."""
        ...


@dataclass(frozen=True)
class VerifiedOwnerApproval:
    approval_id: str
    actor_id: str
    proposal_sha256: str
    commit_sha: str
    issued_at: int
    expires_at: int
    payload_sha256: str


def canonical_approval_payload(artifact: Mapping[str, Any]) -> bytes:
    """Canonical bytes covered by the HMAC signature; signature is excluded."""
    payload = {key: value for key, value in artifact.items() if key != "signature"}
    try:
        return json.dumps(
            payload, sort_keys=True, separators=(",", ":"), ensure_ascii=True,
            allow_nan=False,
        ).encode("utf-8")
    except (TypeError, ValueError) as exc:
        raise OwnerApprovalError("Approval payload is not canonical JSON.") from exc


def sign_approval_payload(artifact: Mapping[str, Any], signing_key: bytes) -> str:
    """Signing primitive for a trusted approval issuer; never expose as a public endpoint."""
    if not isinstance(signing_key, bytes) or len(signing_key) < 32:
        raise OwnerApprovalError("Approval signing key must be at least 32 bytes.")
    return hmac.new(signing_key, canonical_approval_payload(artifact), hashlib.sha256).hexdigest()


class VerifiedOwnerApprovalVerifier:
    def __init__(
        self,
        *,
        signing_key: bytes,
        replay_ledger: ApprovalReplayLedger,
        max_lifetime_seconds: int = 900,
        clock_skew_seconds: int = 30,
        clock: Any = time.time,
    ) -> None:
        if not isinstance(signing_key, bytes) or len(signing_key) < 32:
            raise OwnerApprovalError("Approval signing key must be at least 32 bytes.")
        if max_lifetime_seconds < 1 or clock_skew_seconds < 0:
            raise OwnerApprovalError("Approval lifetime and clock skew configuration is invalid.")
        self._signing_key = signing_key
        self._ledger = replay_ledger
        self._max_lifetime_seconds = max_lifetime_seconds
        self._clock_skew_seconds = clock_skew_seconds
        self._clock = clock

    @classmethod
    def from_env(cls, *, replay_ledger: ApprovalReplayLedger) -> "VerifiedOwnerApprovalVerifier":
        secret = os.environ.get("AIGC_OWNER_APPROVAL_HMAC_KEY", "")
        if not secret:
            raise OwnerApprovalError("Owner approval signing authority is not configured.")
        return cls(signing_key=secret.encode("utf-8"), replay_ledger=replay_ledger)

    def verify_and_consume(
        self,
        artifact: Mapping[str, Any] | None,
        *,
        expected_proposal_sha256: str,
        expected_commit_sha: str,
    ) -> VerifiedOwnerApproval:
        if not isinstance(artifact, Mapping):
            raise OwnerApprovalError("A signed owner approval artifact is required.")
        if not _SHA256.fullmatch(expected_proposal_sha256 or ""):
            raise OwnerApprovalError("Expected proposal digest must be lowercase SHA-256.")
        if not _COMMIT.fullmatch(expected_commit_sha or ""):
            raise OwnerApprovalError("Expected commit must be a full lowercase Git SHA.")

        required_strings = ("approval_id", "actor_id", "proposal_sha256", "commit_sha", "nonce", "signature")
        if any(not isinstance(artifact.get(key), str) or not artifact[key].strip() for key in required_strings):
            raise OwnerApprovalError("Approval artifact is missing a required string field.")
        for key in ("issued_at", "expires_at"):
            if type(artifact.get(key)) is not int:
                raise OwnerApprovalError("Approval timestamps must be integer Unix seconds.")

        approval_id = artifact["approval_id"]
        actor_id = artifact["actor_id"]
        nonce = artifact["nonce"]
        proposal_sha256 = artifact["proposal_sha256"]
        commit_sha = artifact["commit_sha"]
        issued_at = artifact["issued_at"]
        expires_at = artifact["expires_at"]

        if not _SHA256.fullmatch(proposal_sha256):
            raise OwnerApprovalError("Approval proposal digest is invalid.")
        if not _COMMIT.fullmatch(commit_sha):
            raise OwnerApprovalError("Approval commit must be a full lowercase Git SHA.")
        if proposal_sha256 != expected_proposal_sha256 or commit_sha != expected_commit_sha:
            raise OwnerApprovalError("Approval is not bound to the exact expected proposal and commit.")

        signed_bytes = canonical_approval_payload(artifact)
        expected_signature = hmac.new(self._signing_key, signed_bytes, hashlib.sha256).hexdigest()
        supplied_signature = artifact["signature"]
        if not hmac.compare_digest(expected_signature, supplied_signature):
            raise OwnerApprovalError("Owner approval signature is invalid.")

        now = int(self._clock())
        if issued_at > now + self._clock_skew_seconds:
            raise OwnerApprovalError("Owner approval issue time is in the future.")
        if expires_at <= now:
            raise OwnerApprovalError("Owner approval has expired.")
        if expires_at <= issued_at or expires_at - issued_at > self._max_lifetime_seconds:
            raise OwnerApprovalError("Owner approval lifetime is invalid.")

        payload_digest = hashlib.sha256(signed_bytes).hexdigest()
        try:
            consumed = self._ledger.consume_once(
                approval_id=approval_id,
                nonce=nonce,
                payload_sha256=payload_digest,
            )
        except Exception as exc:
            raise OwnerApprovalError("Durable replay protection is unavailable; approval denied.") from exc
        if consumed is not True:
            raise OwnerApprovalError("Owner approval was already consumed or conflicts with prior use.")

        return VerifiedOwnerApproval(
            approval_id=approval_id,
            actor_id=actor_id,
            proposal_sha256=proposal_sha256,
            commit_sha=commit_sha,
            issued_at=issued_at,
            expires_at=expires_at,
            payload_sha256=payload_digest,
        )
