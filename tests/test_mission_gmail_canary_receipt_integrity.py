from __future__ import annotations

from datetime import datetime, timezone
from hashlib import sha256
import json
from pathlib import Path

from jsonschema import Draft202012Validator

from src.mission_os.gmail_canary import account_fingerprint, run_test_canary, write_emergency_stop


def _canonical_digest(value: dict) -> str:
    payload = json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return sha256(payload.encode("utf-8")).hexdigest()


class Provider:
    def __init__(self, email: str) -> None:
        self.email = email
        self.account_fingerprint = account_fingerprint(email)
        self.payload: dict[str, object] = {}
        self.local_revoked = False

    def health(self):
        return {"status": "HEALTHY_DRAFT_ONLY", "send_capability_present": False}

    def create_draft(self, *, to: str, subject: str, body: str, idempotency_key: str):
        self.payload = {"to": to, "subject": subject, "body": body, "sent": False}
        return {"draft_id": "integrity-draft-1"}

    def get_draft(self, draft_id: str):
        assert draft_id == "integrity-draft-1"
        return dict(self.payload)

    def revoke(self):
        self.local_revoked = True
        return {"local_runtime_credential_removed": True, "provider_oauth_grant_revoked": False}


class Revoker:
    def __init__(self, provider: Provider) -> None:
        self.provider = provider
        self.binding: dict | None = None

    def revoke_grant(self, binding):
        assert self.provider.local_revoked is True
        self.binding = dict(binding)
        return {
            "provider": "GOOGLE",
            "oauth_grant_revoked": True,
            "test_account_fingerprint": binding["test_account_fingerprint"],
            "canary_execution_sha256": binding["canary_execution_sha256"],
            "started_audit_receipt_sha256": binding["started_audit_receipt_sha256"],
            "revoked_at": datetime.now(timezone.utc).isoformat(),
            "evidence_reference": "integrity-test-google-revocation",
        }

    def verify_revoked(self, binding):
        return self.binding == dict(binding)


def test_persisted_canary_receipt_is_schema_valid_fully_digest_covered_and_completion_bound(tmp_path: Path) -> None:
    provider = Provider("canary@example.test")
    stop = tmp_path / "stop.json"
    audit = tmp_path / "audit.jsonl"
    receipt_path = tmp_path / "canary.json"
    write_emergency_stop(stop, enabled=True, revision="locked-0001", reason="default locked")

    returned = run_test_canary(
        provider=provider,
        oauth_revoker=Revoker(provider),
        test_account_email=provider.email,
        target_account_fingerprint="b" * 64,
        emergency_stop_path=stop,
        audit_ledger_path=audit,
        canary_receipt_path=receipt_path,
        operator_id="operator-1",
        unlock_revision="unlock-0001",
        relock_revision="relock-0001",
    )

    persisted = json.loads(receipt_path.read_text(encoding="utf-8"))
    schema_path = Path(__file__).resolve().parents[1] / "schemas" / "gmail_test_canary_receipt.schema.json"
    schema = json.loads(schema_path.read_text(encoding="utf-8"))
    Draft202012Validator(schema).validate(persisted)

    assert persisted == returned
    supplied_digest = persisted.pop("receipt_sha256")
    assert supplied_digest == _canonical_digest(persisted)

    records = [json.loads(line) for line in audit.read_text(encoding="utf-8").splitlines()]
    completion = records[-1]
    assert completion["event"] == "CANARY_COMPLETED"
    assert completion["canary_receipt_sha256"] == supplied_digest
    assert "completed_audit_receipt_sha256" not in returned
