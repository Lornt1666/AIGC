"""Governed Gmail test-canary ceremony for Ω Mission OS Increment 10."""
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


class OAuthGrantRevoker(Protocol):
    def revoke_grant(self, binding: Mapping[str, Any]) -> Mapping[str, Any]: ...
    def verify_revoked(self, binding: Mapping[str, Any]) -> bool: ...


def generate_test_activation(*, test_account_email: str, operator_id: str, expires_in_minutes: int = 30) -> dict[str, Any]:
    if not operator_id.strip() or not 1 <= expires_in_minutes <= 60:
        raise ValueError("operator and bounded activation lifetime are required")
    return {
        "schema_version": "1.0.0",
        "status": "ACTIVATED_DRAFT_ONLY",
        "account_fingerprint": account_fingerprint(test_account_email),
        "scope": "https://www.googleapis.com/auth/gmail.compose",
        "environment": "TEST",
        "test_canary_verified": False,
        "send_capability_present": False,
        "emergency_stop_required": True,
        "operator_id": operator_id.strip(),
        "expires_at": _iso(_now() + timedelta(minutes=expires_in_minutes)),
        "revocation_procedure": "Remove local runtime credential, revoke the Google OAuth grant, and verify the revoked grant fails closed.",
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


def _audit_base(operator_id: str, test_fp: str, target_fp: str) -> dict[str, Any]:
    return {
        "schema_version": "1.0.0",
        "recorded_at": _iso(_now()),
        "operator_id": operator_id.strip(),
        "test_account_fingerprint": test_fp,
        "target_account_fingerprint": target_fp,
        "send_authorized": False,
        "send_performed": False,
        "production_activation_authorized": False,
    }


def run_test_canary(
    *,
    provider: DraftOnlyProvider,
    oauth_revoker: OAuthGrantRevoker,
    test_account_email: str,
    target_account_fingerprint: str,
    emergency_stop_path: Path | str,
    audit_ledger_path: Path | str,
    canary_receipt_path: Path | str,
    operator_id: str,
    unlock_revision: str,
    relock_revision: str,
) -> dict[str, Any]:
    test_fp = account_fingerprint(test_account_email)
    if provider.account_fingerprint != test_fp:
        raise PermissionError("provider account does not match the dedicated test account")
    if len(target_account_fingerprint) != 64 or not operator_id.strip():
        raise ValueError("target account binding and operator are required")
    if not load_emergency_stop(emergency_stop_path).enabled:
        raise PermissionError("canary ceremony must begin with the emergency stop enabled")

    audit_path = Path(audit_ledger_path)
    records = _verified_jsonl(audit_path)
    if any(r.get("event") == "CANARY_COMPLETED" and r.get("test_account_fingerprint") == test_fp for r in records):
        raise PermissionError("test-account canary replay is prohibited")

    started = _append_audit(audit_path, {**_audit_base(operator_id, test_fp, target_account_fingerprint), "event": "CANARY_STARTED"})
    write_emergency_stop(emergency_stop_path, enabled=False, revision=unlock_revision, reason="One controlled Gmail test-account draft canary")

    draft_id = ""
    idempotency_key = ""
    execution_sha = ""
    revocation_evidence: dict[str, Any] = {}
    failure: Exception | None = None
    try:
        health = dict(provider.health())
        if health.get("send_capability_present") is not False:
            raise PermissionError("provider health does not prove the no-send boundary")
        subject = "AIGC governed Gmail test canary"
        body = "Controlled test-account draft canary. Do not send."
        normalized_email = test_account_email.strip().lower()
        idempotency_key = sha256(f"{test_fp}:{target_account_fingerprint}:increment-10".encode()).hexdigest()
        draft_id = str(provider.create_draft(to=normalized_email, subject=subject, body=body, idempotency_key=idempotency_key).get("draft_id") or "")
        observed = dict(provider.get_draft(draft_id))
        expected = {"to": normalized_email, "subject": subject, "body": body, "sent": False}
        if any(observed.get(key) != value for key, value in expected.items()):
            raise RuntimeError("Gmail canary read-back verification failed")

        local = dict(provider.revoke())
        if local.get("local_runtime_credential_removed") is not True:
            raise RuntimeError("local runtime credential removal was not verified")

        execution = {
            "test_account_fingerprint": test_fp,
            "target_account_fingerprint": target_account_fingerprint,
            "provider_object_id_sha256": sha256(draft_id.encode()).hexdigest(),
            "idempotency_key": idempotency_key,
            "started_audit_receipt_sha256": started["audit_receipt_sha256"],
            "readback_verified_at": _iso(_now()),
        }
        execution_sha = _digest(execution)
        binding = {**execution, "canary_execution_sha256": execution_sha}
        revocation_evidence = dict(oauth_revoker.revoke_grant(binding))
        required = {
            "provider": "GOOGLE",
            "oauth_grant_revoked": True,
            "test_account_fingerprint": test_fp,
            "canary_execution_sha256": execution_sha,
            "started_audit_receipt_sha256": started["audit_receipt_sha256"],
        }
        if any(revocation_evidence.get(k) != v for k, v in required.items()) or not revocation_evidence.get("revoked_at") or not revocation_evidence.get("evidence_reference"):
            raise PermissionError("provider OAuth revocation evidence is incomplete or not bound to this canary")
        if oauth_revoker.verify_revoked(binding) is not True:
            raise PermissionError("revoked OAuth grant did not fail closed")
    except Exception as exc:
        failure = exc
        raise
    finally:
        write_emergency_stop(emergency_stop_path, enabled=True, revision=relock_revision, reason="Gmail canary terminal state; connector relocked")
        _append_audit(audit_path, {
            **_audit_base(operator_id, test_fp, target_account_fingerprint),
            "event": "CANARY_RELOCKED",
            "relock_revision": relock_revision,
            "outcome": "FAILURE" if failure else "SUCCESS",
        })
        if failure is not None:
            _append_audit(audit_path, {
                **_audit_base(operator_id, test_fp, target_account_fingerprint),
                "event": "CANARY_FAILED",
                "failure_type": type(failure).__name__,
                "failure_message_sha256": sha256(str(failure).encode()).hexdigest(),
            })

    receipt_body = {
        "schema_version": "1.0.0", "result": CANARY_RESULT, "provider": "GMAIL", "action_type": "CREATE_DRAFT",
        "test_account_fingerprint": test_fp, "target_account_fingerprint": target_account_fingerprint,
        "provider_verified": True, "sent": False, "external_action_performed": True,
        "verified_at": _iso(_now()), "expires_at": _iso(_now() + timedelta(days=7)),
        "provider_object_id_sha256": sha256(draft_id.encode()).hexdigest(), "idempotency_key": idempotency_key,
        "canary_execution_sha256": execution_sha, "started_audit_receipt_sha256": started["audit_receipt_sha256"],
        "local_runtime_credential_removed": True, "provider_oauth_grant_revoked": True,
        "provider_revocation_evidence_sha256": _digest(revocation_evidence), "revoked_grant_verified_unusable": True,
        "emergency_stop_relocked": True, "production_activation_authorized": False, "terminal_state": TERMINAL_STATE,
    }
    receipt = {**receipt_body, "receipt_sha256": _digest(receipt_body)}
    target = Path(canary_receipt_path)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(receipt, sort_keys=True, indent=2) + "\n", encoding="utf-8")
    _append_audit(audit_path, {
        **_audit_base(operator_id, test_fp, target_account_fingerprint),
        "event": "CANARY_COMPLETED", "canary_execution_sha256": execution_sha,
        "canary_receipt_sha256": receipt["receipt_sha256"],
        "provider_revocation_evidence_sha256": receipt["provider_revocation_evidence_sha256"],
    })
    return receipt
