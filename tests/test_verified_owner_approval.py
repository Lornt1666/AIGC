from __future__ import annotations
import hashlib

import pytest

from src.core.verified_owner_approval import (
    OwnerApprovalError,
    VerifiedOwnerApprovalVerifier,
    sign_approval_payload,
)


KEY = b"test-only-owner-approval-key-material-32-bytes-minimum"
PROPOSAL = hashlib.sha256(b"immutable proposal").hexdigest()
COMMIT = "a" * 40
NOW = 1_800_000_000


class FakeReplayLedger:
    def __init__(self):
        self.consumed = set()

    def consume_once(self, *, approval_id, nonce, payload_sha256):
        key = (approval_id, nonce)
        if key in self.consumed:
            return False
        self.consumed.add(key)
        return True


class UnavailableLedger:
    def consume_once(self, **_kwargs):
        raise RuntimeError("database unavailable")


def make_artifact(**overrides):
    artifact = {
        "approval_id": "approval-001",
        "actor_id": "owner:verified-subject",
        "proposal_sha256": PROPOSAL,
        "commit_sha": COMMIT,
        "issued_at": NOW - 5,
        "expires_at": NOW + 300,
        "nonce": "unique-nonce-001",
    }
    artifact.update(overrides)
    artifact["signature"] = sign_approval_payload(artifact, KEY)
    return artifact


def verifier(ledger=None):
    return VerifiedOwnerApprovalVerifier(
        signing_key=KEY,
        replay_ledger=ledger or FakeReplayLedger(),
        max_lifetime_seconds=900,
        clock_skew_seconds=30,
        clock=lambda: NOW,
    )


def test_valid_approval_is_bound_and_consumed():
    ledger = FakeReplayLedger()
    result = verifier(ledger).verify_and_consume(
        make_artifact(),
        expected_proposal_sha256=PROPOSAL,
        expected_commit_sha=COMMIT,
    )
    assert result.approval_id == "approval-001"
    assert result.actor_id == "owner:verified-subject"
    assert result.proposal_sha256 == PROPOSAL
    assert result.commit_sha == COMMIT
    assert len(result.payload_sha256) == 64


@pytest.mark.parametrize(
    "kwargs",
    [
        {"expected_proposal_sha256": hashlib.sha256(b"other proposal").hexdigest()},
        {"expected_commit_sha": "b" * 40},
    ],
)
def test_mismatched_proposal_or_commit_is_rejected(kwargs):
    expected = {"expected_proposal_sha256": PROPOSAL, "expected_commit_sha": COMMIT}
    expected.update(kwargs)
    with pytest.raises(OwnerApprovalError, match="not bound"):
        verifier().verify_and_consume(make_artifact(), **expected)


def test_approval_actor_must_match_authenticated_operator():
    with pytest.raises(OwnerApprovalError, match="actor does not match"):
        verifier().verify_and_consume(
            make_artifact(),
            expected_proposal_sha256=PROPOSAL,
            expected_commit_sha=COMMIT,
            expected_actor_id="token-sha256:some-other-operator",
        )


def test_tampered_signature_is_rejected():
    artifact = make_artifact()
    artifact["actor_id"] = "owner:attacker"
    with pytest.raises(OwnerApprovalError, match="signature is invalid"):
        verifier().verify_and_consume(
            artifact,
            expected_proposal_sha256=PROPOSAL,
            expected_commit_sha=COMMIT,
        )


def test_expired_approval_is_rejected():
    artifact = make_artifact(expires_at=NOW - 1)
    with pytest.raises(OwnerApprovalError, match="expired"):
        verifier().verify_and_consume(
            artifact,
            expected_proposal_sha256=PROPOSAL,
            expected_commit_sha=COMMIT,
        )


def test_future_issued_approval_is_rejected():
    artifact = make_artifact(issued_at=NOW + 60, expires_at=NOW + 300)
    with pytest.raises(OwnerApprovalError, match="future"):
        verifier().verify_and_consume(
            artifact,
            expected_proposal_sha256=PROPOSAL,
            expected_commit_sha=COMMIT,
        )


def test_excessive_lifetime_is_rejected():
    artifact = make_artifact(expires_at=NOW + 901)
    with pytest.raises(OwnerApprovalError, match="lifetime"):
        verifier().verify_and_consume(
            artifact,
            expected_proposal_sha256=PROPOSAL,
            expected_commit_sha=COMMIT,
        )


def test_replayed_approval_is_rejected():
    ledger = FakeReplayLedger()
    instance = verifier(ledger)
    artifact = make_artifact()
    instance.verify_and_consume(
        artifact,
        expected_proposal_sha256=PROPOSAL,
        expected_commit_sha=COMMIT,
    )
    with pytest.raises(OwnerApprovalError, match="already consumed"):
        instance.verify_and_consume(
            artifact,
            expected_proposal_sha256=PROPOSAL,
            expected_commit_sha=COMMIT,
        )


def test_replay_ledger_outage_fails_closed():
    with pytest.raises(OwnerApprovalError, match="replay protection is unavailable"):
        verifier(UnavailableLedger()).verify_and_consume(
            make_artifact(),
            expected_proposal_sha256=PROPOSAL,
            expected_commit_sha=COMMIT,
        )


def test_missing_artifact_is_rejected():
    with pytest.raises(OwnerApprovalError, match="artifact is required"):
        verifier().verify_and_consume(
            None,
            expected_proposal_sha256=PROPOSAL,
            expected_commit_sha=COMMIT,
        )


def test_short_signing_key_is_rejected():
    with pytest.raises(OwnerApprovalError, match="at least 32 bytes"):
        VerifiedOwnerApprovalVerifier(
            signing_key=b"short",
            replay_ledger=FakeReplayLedger(),
        )
