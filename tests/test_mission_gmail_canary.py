from __future__ import annotations

from datetime import datetime, timezone
from hashlib import sha256
import json
from pathlib import Path

import pytest

from src.mission_os.gmail_canary import TERMINAL_STATE, account_fingerprint, generate_test_activation, run_test_canary, write_emergency_stop


class Provider:
    def __init__(self, email: str) -> None:
        self.account_fingerprint = account_fingerprint(email)
        self.email = email
        self.created = 0
        self.revoked = False
        self.payload = None
        self.order: list[str] = []

    def health(self):
        self.order.append("health")
        return {"status": "HEALTHY_DRAFT_ONLY", "send_capability_present": False}

    def create_draft(self, *, to: str, subject: str, body: str, idempotency_key: str):
        self.order.append("create")
        self.created += 1
        self.payload = {"to": to, "subject": subject, "body": body, "sent": False, "idempotency_key": idempotency_key}
        return {"draft_id": "draft-canary-1"}

    def get_draft(self, draft_id: str):
        self.order.append("readback")
        return {key: self.payload[key] for key in ("to", "subject", "body", "sent")}

    def revoke(self):
        self.order.append("local-revoke")
        self.revoked = True
        return {"local_runtime_credential_removed": True, "provider_oauth_grant_revoked": False}


class Revoker:
    def __init__(self, provider: Provider, *, verified: bool = True, mutate: bool = False) -> None:
        self.provider = provider
        self.verified = verified
        self.mutate = mutate
        self.binding = None

    def revoke_grant(self, binding):
        assert self.provider.revoked is True
        self.provider.order.append("provider-revoke")
        self.binding = dict(binding)
        evidence = {
            "provider": "GOOGLE",
            "oauth_grant_revoked": True,
            "test_account_fingerprint": binding["test_account_fingerprint"],
            "canary_execution_sha256": binding["canary_execution_sha256"],
            "started_audit_receipt_sha256": binding["started_audit_receipt_sha256"],
            "revoked_at": datetime.now(timezone.utc).isoformat(),
            "evidence_reference": "google-revocation-receipt-1",
        }
        if self.mutate:
            evidence["canary_execution_sha256"] = "0" * 64
        return evidence

    def verify_revoked(self, binding):
        self.provider.order.append("verify-revoked")
        return self.verified and self.binding == dict(binding)


def _run(tmp_path: Path, provider: Provider, revoker: Revoker | None = None):
    stop = tmp_path / "stop.json"
    write_emergency_stop(stop, enabled=True, revision="locked-0001", reason="default locked")
    return run_test_canary(
        provider=provider,
        oauth_revoker=revoker or Revoker(provider),
        test_account_email=provider.email,
        target_account_fingerprint="b" * 64,
        emergency_stop_path=stop,
        audit_ledger_path=tmp_path / "audit.jsonl",
        canary_receipt_path=tmp_path / "canary.json",
        operator_id="operator-1",
        unlock_revision="unlock-0001",
        relock_revision="relock-0001",
    )


def test_activation_is_pre_canary_and_not_verified() -> None:
    fp = account_fingerprint(" Canary@Example.Test ")
    assert fp == sha256(b"canary@example.test").hexdigest()
    activation = generate_test_activation(test_account_email="canary@example.test", operator_id="operator-1")
    assert activation["environment"] == "TEST"
    assert activation["test_canary_verified"] is False
    assert activation["production_activation_authorized"] is False


def test_canary_orders_revocation_after_readback_and_local_removal(tmp_path: Path) -> None:
    provider = Provider("canary@example.test")
    receipt = _run(tmp_path, provider)
    assert provider.order == ["health", "create", "readback", "local-revoke", "provider-revoke", "verify-revoked"]
    assert receipt["terminal_state"] == TERMINAL_STATE
    assert receipt["revoked_grant_verified_unusable"] is True
    assert receipt["production_activation_authorized"] is False
    assert json.loads((tmp_path / "stop.json").read_text())["enabled"] is True
    events = [json.loads(line)["event"] for line in (tmp_path / "audit.jsonl").read_text().splitlines()]
    assert events == ["CANARY_STARTED", "CANARY_RELOCKED", "CANARY_COMPLETED"]


def test_canary_requires_locked_start(tmp_path: Path) -> None:
    provider = Provider("canary@example.test")
    stop = tmp_path / "stop.json"
    write_emergency_stop(stop, enabled=False, revision="open-0001", reason="incorrect")
    with pytest.raises(PermissionError, match="begin with the emergency stop enabled"):
        run_test_canary(provider=provider, oauth_revoker=Revoker(provider), test_account_email=provider.email,
            target_account_fingerprint="b" * 64, emergency_stop_path=stop, audit_ledger_path=tmp_path / "audit.jsonl",
            canary_receipt_path=tmp_path / "canary.json", operator_id="operator-1",
            unlock_revision="unlock-0001", relock_revision="relock-0001")


def test_account_mismatch_fails_before_external_effect(tmp_path: Path) -> None:
    provider = Provider("wrong@example.test")
    stop = tmp_path / "stop.json"
    write_emergency_stop(stop, enabled=True, revision="locked-0001", reason="default locked")
    with pytest.raises(PermissionError, match="dedicated test account"):
        run_test_canary(provider=provider, oauth_revoker=Revoker(provider), test_account_email="canary@example.test",
            target_account_fingerprint="b" * 64, emergency_stop_path=stop, audit_ledger_path=tmp_path / "audit.jsonl",
            canary_receipt_path=tmp_path / "canary.json", operator_id="operator-1",
            unlock_revision="unlock-0001", relock_revision="relock-0001")
    assert provider.created == 0


def test_revocation_evidence_must_bind_exact_execution(tmp_path: Path) -> None:
    provider = Provider("canary@example.test")
    with pytest.raises(PermissionError, match="not bound"):
        _run(tmp_path, provider, Revoker(provider, mutate=True))
    events = [json.loads(line)["event"] for line in (tmp_path / "audit.jsonl").read_text().splitlines()]
    assert events[-2:] == ["CANARY_RELOCKED", "CANARY_FAILED"]


def test_revoked_grant_must_fail_closed(tmp_path: Path) -> None:
    provider = Provider("canary@example.test")
    with pytest.raises(PermissionError, match="did not fail closed"):
        _run(tmp_path, provider, Revoker(provider, verified=False))
    assert json.loads((tmp_path / "stop.json").read_text())["enabled"] is True
    events = [json.loads(line)["event"] for line in (tmp_path / "audit.jsonl").read_text().splitlines()]
    assert events[-2:] == ["CANARY_RELOCKED", "CANARY_FAILED"]


def test_readback_failure_relocks_and_records_terminal_failure(tmp_path: Path) -> None:
    class BadProvider(Provider):
        def get_draft(self, draft_id: str):
            value = super().get_draft(draft_id)
            value["sent"] = True
            return value

    provider = BadProvider("canary@example.test")
    with pytest.raises(RuntimeError, match="read-back"):
        _run(tmp_path, provider)
    assert provider.revoked is False
    events = [json.loads(line)["event"] for line in (tmp_path / "audit.jsonl").read_text().splitlines()]
    assert events == ["CANARY_STARTED", "CANARY_RELOCKED", "CANARY_FAILED"]


def test_completed_canary_cannot_be_replayed(tmp_path: Path) -> None:
    _run(tmp_path, Provider("canary@example.test"))
    provider2 = Provider("canary@example.test")
    with pytest.raises(PermissionError, match="replay"):
        _run(tmp_path, provider2)
    assert provider2.created == 0


def test_audit_tampering_fails_closed(tmp_path: Path) -> None:
    _run(tmp_path, Provider("canary@example.test"))
    audit = tmp_path / "audit.jsonl"
    records = audit.read_text().splitlines()
    first = json.loads(records[0]); first["operator_id"] = "tampered"; records[0] = json.dumps(first)
    audit.write_text("\n".join(records) + "\n")
    stop = tmp_path / "stop.json"
    write_emergency_stop(stop, enabled=True, revision="locked-0002", reason="default locked")
    provider = Provider("canary@example.test")
    with pytest.raises(ValueError, match="integrity"):
        run_test_canary(provider=provider, oauth_revoker=Revoker(provider), test_account_email=provider.email,
            target_account_fingerprint="b" * 64, emergency_stop_path=stop, audit_ledger_path=audit,
            canary_receipt_path=tmp_path / "canary2.json", operator_id="operator-1",
            unlock_revision="unlock-0002", relock_revision="relock-0002")
