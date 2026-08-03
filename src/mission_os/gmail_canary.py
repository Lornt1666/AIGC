"""Governed Gmail test-canary ceremony for Ω Mission OS Increment 10.

This module prepares and records a single test-account draft canary. It never
sends email and never enables production. Live provider calls remain delegated
to the Increment 8/9 draft-only provider contract.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from hashlib import sha256
import hmac
import json
from pathlib import Path
from typing import Any, Mapping, Protocol

from src.mission_os.external_gateway import load_emergency_stop

TERMINAL_STATE = "CANARY_VERIFIED_NOT_PRODUCTION_ENABLED"
CANARY_RESULT = "DRAFT_CREATED_NOT_SENT"


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _iso(value: datetime) -> str:
    return value.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


def _digest(value: Mapping[str, Any]) -> str:
    payload = json.dumps(dict(value), sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return sha256(payload.encode("utf-8")).hexdigest()


def account_fingerprint(email: str) -> str:
    normalized = email.strip().lower()
    if "@" not in normalized or len(normalized) < 3:
        raise ValueError("valid test-account email is required")
    return sha256(normalized.encode("utf-8")).hexdigest()


def _load_object(path: Path | str) -> dict[str, Any]:
    value = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError("canary record must be an object")
    return value


def _verified_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.is_file():
        return []
    records: list[dict[str, Any]] = []
    previous: str | None = None
    for line in path.read_text(encoding="utf-8").splitlines():
        record = json.loads(line)
        if not isinstance(record, dict):
            raise ValueError("canary audit ledger contains a non-object record")
        supplied = record.get("audit_receipt_sha256")
        body = {key: value for key, value in record.items() if key != "audit_receipt_sha256"}
        if body.get("previous_receipt_sha256") != previous or not isinstance(supplied, str) or not hmac.compare_digest(supplied, _digest(body)):
            raise ValueError("canary audit ledger integrity verification failed")
        records.append(record)
        previous = supplied
    return records


def _append_audit(path: Path, event: Mapping[str, Any]) -> dict[str, Any]:
    records = _verified_jsonl(path)
    value = dict(event)
    value["previous_receipt_sha256"] = records[-1]["audit_receipt_sha256"] if records else None
    value["audit_receipt_sha256"] = _digest(value)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(value, sort_keys=True, ensure_ascii=False) + "\n")
    return value


class DraftOnlyProvider(Protocol):
    account_fingerprint: str
    def health(self) -> Mapping[str, Any]: ...
    def create_draft(self, *, to: str, subject: str, body: str, idempotency_key: str) -> Mapping[str, Any]: ...
    def get_draft(self, draft_id: str) -> Mapping[str, Any]: ...
    def revoke(self) -> Mapping[str, Any]: ...


def generate_test_activation(*, test_account_email: str, operator_id: str, expires_in_minutes: int = 30) -> dict[str, Any]:
    if not operator_id.strip() or not 1 <= expires_in_minutes <= 60:
        raise ValueError("operator and bounded activation lifetime are required")
    fingerprint = account_fingerprint(test_account_email)
    return {
        "schema_version": "1.0.0",
        "status": "ACTIVATED_DRAFT_ONLY",
        "account_fingerprint": fingerprint,
        "scope": "https://www.googleapis.com/auth/gmail.compose",
        "environment": "TEST",
        "test_canary_verified": True,
        "send_capability_present": False,
        "emergency_stop_required": True,
        "operator_id": operator_id.strip(),
        "expires_at": _iso(_now() + timedelta(minutes=expires_in_minutes)),
        "revocation_procedure": "Remove local runtime credential and separately revoke the Google OAuth grant.",
        "production_activation_authorized": False,
    }


def write_emergency_stop(path: Path | str, *, enabled: bool, revision: str, reason: str) -> dict[str, Any]:
    if len(revision) < 8 or not reason.strip():
        raise ValueError("bounded emergency-stop revision and reason are required")
    value = {"schema_version": "1.0.0", "enabled": enabled, "revision": revision, "reason": reason.strip()}
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(value, sort_keys=True, indent=2) + "\n", encoding="utf-8")
    return value


def run_test_canary(
    *,
    provider: DraftOnlyProvider,
    test_account_email: str,
    target_account_fingerprint: str,
    emergency_stop_path: Path | str,
    audit_ledger_path: Path | str,
    canary_receipt_path: Path | str,
    provider_revocation_evidence: Mapping[str, Any],
    operator_id: str,
    unlock_revision: str,
    relock_revision: str,
) -> dict[str, Any]:
    test_fp = account_fingerprint(test_account_email)
    if provider.account_fingerprint != test_fp:
        raise PermissionError("provider account does not match the dedicated test account")
    if len(target_account_fingerprint) != 64 or not operator_id.strip():
        raise ValueError("target account binding and operator are required")
    if provider_revocation_evidence.get("provider") != "GOOGLE" or provider_revocation_evidence.get("oauth_grant_revoked") is not True:
        raise PermissionError("provider-side OAuth revocation evidence is required")
    if not provider_revocation_evidence.get("evidence_reference"):
        raise PermissionError("provider-side OAuth revocation evidence reference is required")

    stop = load_emergency_stop(emergency_stop_path)
    if not stop.enabled:
        raise PermissionError("canary ceremony must begin with the emergency stop enabled")

    audit_path = Path(audit_ledger_path)
    if any(record.get("event") == "CANARY_COMPLETED" and record.get("test_account_fingerprint") == test_fp for record in _verified_jsonl(audit_path)):
        raise PermissionError("test-account canary replay is prohibited")

    _append_audit(audit_path, {
        "schema_version": "1.0.0", "event": "CANARY_STARTED", "recorded_at": _iso(_now()),
        "operator_id": operator_id.strip(), "test_account_fingerprint": test_fp,
        "target_account_fingerprint": target_account_fingerprint, "send_authorized": False,
    })

    write_emergency_stop(emergency_stop_path, enabled=False, revision=unlock_revision, reason="One controlled Gmail test-account draft canary")
    try:
        health = dict(provider.health())
        if health.get("send_capability_present") is not False:
            raise PermissionError("provider health does not prove the no-send boundary")
        subject = "AIGC governed Gmail test canary"
        body = "Controlled test-account draft canary. Do not send."
        idempotency_key = sha256(f"{test_fp}:{target_account_fingerprint}:increment-10".encode("utf-8")).hexdigest()
        created = provider.create_draft(to=test_account_email.strip().lower(), subject=subject, body=body, idempotency_key=idempotency_key)
        draft_id = str(created.get("draft_id") or "")
        observed = dict(provider.get_draft(draft_id))
        expected = {"to": test_account_email.strip().lower(), "subject": subject, "body": body, "sent": False}
        if any(observed.get(key) != value for key, value in expected.items()):
            raise RuntimeError("Gmail canary read-back verification failed")
        local_revocation = dict(provider.revoke())
        if local_revocation.get("local_runtime_credential_removed") is not True:
            raise RuntimeError("local runtime credential removal was not verified")
    finally:
        write_emergency_stop(emergency_stop_path, enabled=True, revision=relock_revision, reason="Gmail canary completed; connector relocked")

    receipt_body = {
        "schema_version": "1.0.0",
        "result": CANARY_RESULT,
        "provider": "GMAIL",
        "action_type": "CREATE_DRAFT",
        "test_account_fingerprint": test_fp,
        "target_account_fingerprint": target_account_fingerprint,
        "provider_verified": True,
        "sent": False,
        "external_action_performed": True,
        "verified_at": _iso(_now()),
        "expires_at": _iso(_now() + timedelta(days=7)),
        "provider_object_id_sha256": sha256(draft_id.encode("utf-8")).hexdigest(),
        "idempotency_key": idempotency_key,
        "local_runtime_credential_removed": True,
        "provider_oauth_grant_revoked": True,
        "provider_revocation_evidence_sha256": _digest(dict(provider_revocation_evidence)),
        "emergency_stop_relocked": True,
        "production_activation_authorized": False,
        "terminal_state": TERMINAL_STATE,
    }
    receipt = dict(receipt_body)
    receipt["receipt_sha256"] = _digest(receipt_body)
    target = Path(canary_receipt_path)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(receipt, sort_keys=True, indent=2) + "\n", encoding="utf-8")
    _append_audit(audit_path, {
        "schema_version": "1.0.0", "event": "CANARY_COMPLETED", "recorded_at": _iso(_now()),
        "operator_id": operator_id.strip(), "test_account_fingerprint": test_fp,
        "target_account_fingerprint": target_account_fingerprint,
        "canary_receipt_sha256": receipt["receipt_sha256"], "send_performed": False,
        "production_activation_authorized": False,
    })
    return receipt
