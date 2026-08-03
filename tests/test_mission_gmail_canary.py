from __future__ import annotations

from hashlib import sha256
import json
from pathlib import Path

import pytest

from src.mission_os.gmail_canary import (
    TERMINAL_STATE,
    account_fingerprint,
    generate_test_activation,
    run_test_canary,
    write_emergency_stop,
)


class Provider:
    def __init__(self, email: str) -> None:
        self.account_fingerprint = account_fingerprint(email)
        self.email = email
        self.created = 0
        self.revoked = False
        self.payload = None

    def health(self):
        return {"status": "HEALTHY_DRAFT_ONLY", "send_capability_present": False}

    def create_draft(self, *, to: str, subject: str, body: str, idempotency_key: str):
        self.created += 1
        self.payload = {"to": to, "subject": subject, "body": body, "sent": False, "idempotency_key": idempotency_key}
        return {"draft_id": "draft-canary-1"}

    def get_draft(self, draft_id: str):
        assert draft_id == "draft-canary-1"
        return {key: self.payload[key] for key in ("to", "subject", "body", "sent")}

    def revoke(self):
        self.revoked = True
        return {
            "status": "LOCAL_RUNTIME_CREDENTIAL_REMOVED_PROVIDER_REVOCATION_REQUIRED",
            "local_runtime_credential_removed": True,
            "provider_oauth_grant_revoked": False,
        }


def _revocation():
    return {"provider": "GOOGLE", "oauth_grant_revoked": True, "evidence_reference": "operator-confirmed-google-revocation"}


def _run(tmp_path: Path, provider: Provider):
    stop = tmp_path / "stop.json"
    write_emergency_stop(stop, enabled=True, revision="locked-0001", reason="default locked")
    return run_test_canary(
        provider=provider,
        test_account_email=provider.email,
        target_account_fingerprint="b" * 64,
        emergency_stop_path=stop,
        audit_ledger_path=tmp_path / "audit.jsonl",
        canary_receipt_path=tmp_path / "canary.json",
        provider_revocation_evidence=_revocation(),
        operator_id="operator-1",
        unlock_revision="unlock-0001",
        relock_revision="relock-0001",
    )


def test_account_fingerprint_and_activation_are_bounded() -> None:
    fp = account_fingerprint(" Canary@Example.Test ")
    assert fp == sha256(b"canary@example.test").hexdigest()
    activation = generate_test_activation(test_account_email="canary@example.test", operator_id="operator-1")
    assert activation["environment"] == "TEST"
    assert activation["send_capability_present"] is False
    assert activation["production_activation_authorized"] is False


def test_canary_creates_one_verified_unsent_draft_and_relocks(tmp_path: Path) -> None:
    provider = Provider("canary@example.test")
    receipt = _run(tmp_path, provider)
    assert provider.created == 1
    assert provider.revoked is True
    assert receipt["terminal_state"] == TERMINAL_STATE
    assert receipt["sent"] is False
    assert receipt["provider_verified"] is True
    assert receipt["production_activation_authorized"] is False
    assert len(receipt["receipt_sha256"]) == 64
    stop = json.loads((tmp_path / "stop.json").read_text())
    assert stop["enabled"] is True
    assert stop["revision"] == "relock-0001"


def test_canary_requires_locked_start(tmp_path: Path) -> None:
    provider = Provider("canary@example.test")
    stop = tmp_path / "stop.json"
    write_emergency_stop(stop, enabled=False, revision="open-0001", reason="incorrect")
    with pytest.raises(PermissionError, match="begin with the emergency stop enabled"):
        run_test_canary(
            provider=provider,
            test_account_email=provider.email,
            target_account_fingerprint="b" * 64,
            emergency_stop_path=stop,
            audit_ledger_path=tmp_path / "audit.jsonl",
            canary_receipt_path=tmp_path / "canary.json",
            provider_revocation_evidence=_revocation(),
            operator_id="operator-1",
            unlock_revision="unlock-0001",
            relock_revision="relock-0001",
        )


def test_canary_requires_provider_revocation_evidence(tmp_path: Path) -> None:
    provider = Provider("canary@example.test")
    stop = tmp_path / "stop.json"
    write_emergency_stop(stop, enabled=True, revision="locked-0001", reason="default locked")
    with pytest.raises(PermissionError, match="provider-side OAuth revocation"):
        run_test_canary(
            provider=provider,
            test_account_email=provider.email,
            target_account_fingerprint="b" * 64,
            emergency_stop_path=stop,
            audit_ledger_path=tmp_path / "audit.jsonl",
            canary_receipt_path=tmp_path / "canary.json",
            provider_revocation_evidence={"provider": "GOOGLE", "oauth_grant_revoked": False},
            operator_id="operator-1",
            unlock_revision="unlock-0001",
            relock_revision="relock-0001",
        )


def test_account_mismatch_fails_before_external_effect(tmp_path: Path) -> None:
    provider = Provider("wrong@example.test")
    stop = tmp_path / "stop.json"
    write_emergency_stop(stop, enabled=True, revision="locked-0001", reason="default locked")
    with pytest.raises(PermissionError, match="dedicated test account"):
        run_test_canary(
            provider=provider,
            test_account_email="canary@example.test",
            target_account_fingerprint="b" * 64,
            emergency_stop_path=stop,
            audit_ledger_path=tmp_path / "audit.jsonl",
            canary_receipt_path=tmp_path / "canary.json",
            provider_revocation_evidence=_revocation(),
            operator_id="operator-1",
            unlock_revision="unlock-0001",
            relock_revision="relock-0001",
        )
    assert provider.created == 0


def test_readback_failure_still_relocks(tmp_path: Path) -> None:
    class BadProvider(Provider):
        def get_draft(self, draft_id: str):
            value = super().get_draft(draft_id)
            value["sent"] = True
            return value

    provider = BadProvider("canary@example.test")
    stop = tmp_path / "stop.json"
    write_emergency_stop(stop, enabled=True, revision="locked-0001", reason="default locked")
    with pytest.raises(RuntimeError, match="read-back"):
        run_test_canary(
            provider=provider,
            test_account_email=provider.email,
            target_account_fingerprint="b" * 64,
            emergency_stop_path=stop,
            audit_ledger_path=tmp_path / "audit.jsonl",
            canary_receipt_path=tmp_path / "canary.json",
            provider_revocation_evidence=_revocation(),
            operator_id="operator-1",
            unlock_revision="unlock-0001",
            relock_revision="relock-0001",
        )
    assert json.loads(stop.read_text())["enabled"] is True


def test_completed_canary_cannot_be_replayed(tmp_path: Path) -> None:
    provider = Provider("canary@example.test")
    _run(tmp_path, provider)
    provider2 = Provider("canary@example.test")
    with pytest.raises(PermissionError, match="replay"):
        _run(tmp_path, provider2)
    assert provider2.created == 0


def test_audit_tampering_fails_closed(tmp_path: Path) -> None:
    provider = Provider("canary@example.test")
    _run(tmp_path, provider)
    audit = tmp_path / "audit.jsonl"
    records = audit.read_text().splitlines()
    first = json.loads(records[0])
    first["operator_id"] = "tampered"
    records[0] = json.dumps(first)
    audit.write_text("\n".join(records) + "\n")
    stop = tmp_path / "stop.json"
    write_emergency_stop(stop, enabled=True, revision="locked-0002", reason="default locked")
    with pytest.raises(ValueError, match="integrity"):
        run_test_canary(
            provider=Provider("canary@example.test"),
            test_account_email="canary@example.test",
            target_account_fingerprint="b" * 64,
            emergency_stop_path=stop,
            audit_ledger_path=audit,
            canary_receipt_path=tmp_path / "canary2.json",
            provider_revocation_evidence=_revocation(),
            operator_id="operator-1",
            unlock_revision="unlock-0002",
            relock_revision="relock-0002",
        )
