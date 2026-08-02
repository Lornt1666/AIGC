"""Governed single-action Gmail draft gateway for Ω Mission OS Increment 8.

The only supported external effect is creating a Gmail draft and verifying it.
No send capability exists. Providers are dependency-injected; credentials never
enter packets, approvals, logs, or receipts.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from hashlib import sha256
import hmac
import json
from pathlib import Path
from typing import Any, Mapping, Protocol

from src.mission_os.decisions import verify_operator_credential

ALLOWED_CONNECTOR = "GMAIL"
ALLOWED_ACTION = "CREATE_DRAFT"
TERMINAL_STATE = "DRAFT_CREATED_NOT_SENT"
UNCERTAIN_STATE = "DRAFT_CREATION_OUTCOME_UNKNOWN"
RESERVED_STATE = "EXECUTION_ATTEMPT_RESERVED"


def _now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _parse_utc(value: str) -> datetime:
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise ValueError("expiry must be a valid ISO-8601 date-time") from exc
    if parsed.tzinfo is None:
        raise ValueError("expiry must include a timezone")
    return parsed.astimezone(timezone.utc)


def _digest(value: Mapping[str, Any]) -> str:
    payload = json.dumps(dict(value), sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return sha256(payload.encode("utf-8")).hexdigest()


def _runtime_path(root: Path, configured: Path | str | None, filename: str) -> Path:
    path = (Path(configured) if configured is not None else root / ".aigc" / "mission_os" / filename).resolve()
    forbidden = [root / "data", root / "memory", root / "governance", root / "config"]
    if any(path == item.resolve() or item.resolve() in path.parents for item in forbidden):
        raise ValueError("gateway runtime records must remain outside canonical state roots")
    return path


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.is_file():
        return []
    records: list[dict[str, Any]] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        value = json.loads(line)
        if not isinstance(value, dict):
            raise ValueError("gateway ledger contains a non-object record")
        records.append(value)
    return records


def _verified_chain(path: Path, receipt_field: str) -> list[dict[str, Any]]:
    records = _read_jsonl(path)
    previous: str | None = None
    for record in records:
        supplied = record.get(receipt_field)
        body = {key: value for key, value in record.items() if key != receipt_field}
        valid = (
            body.get("previous_receipt_sha256") == previous
            and isinstance(supplied, str)
            and hmac.compare_digest(supplied, _digest(body))
        )
        if not valid:
            raise ValueError("gateway ledger integrity verification failed")
        previous = supplied
    return records


def _append_chained(path: Path, body: Mapping[str, Any], receipt_field: str) -> dict[str, Any]:
    records = _verified_chain(path, receipt_field)
    value = dict(body)
    value["previous_receipt_sha256"] = records[-1][receipt_field] if records else None
    value[receipt_field] = _digest(value)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(value, sort_keys=True, ensure_ascii=False) + "\n")
    return value


class GmailDraftProvider(Protocol):
    account_fingerprint: str

    def create_draft(self, *, to: str, subject: str, body: str, idempotency_key: str) -> Mapping[str, Any]: ...
    def get_draft(self, draft_id: str) -> Mapping[str, Any]: ...


@dataclass(frozen=True)
class EmergencyStop:
    enabled: bool
    revision: str
    reason: str


def load_emergency_stop(path: Path | str) -> EmergencyStop:
    target = Path(path)
    if not target.is_file():
        raise ValueError("emergency-stop state is unavailable")
    value = json.loads(target.read_text(encoding="utf-8"))
    if not isinstance(value, dict) or value.get("schema_version") != "1.0.0":
        raise ValueError("emergency-stop state is invalid")
    enabled = value.get("enabled")
    revision = value.get("revision")
    reason = value.get("reason")
    if not isinstance(enabled, bool) or not isinstance(revision, str) or len(revision) < 8 or not isinstance(reason, str):
        raise ValueError("emergency-stop state is incomplete")
    return EmergencyStop(enabled=enabled, revision=revision, reason=reason)


def _packet_payload(packet: Mapping[str, Any]) -> dict[str, str]:
    return {
        "to": str(packet.get("submission_channel") or ""),
        "subject": str(packet.get("title") or "Proposal"),
        "body": str(packet.get("message_body") or ""),
    }


def create_third_stage_approval(
    repository_root: Path | str,
    request: Mapping[str, Any],
    *,
    operator_credential: str | None,
    expected_credential: str | None,
    packet_ledger_path: Path | str,
    second_stage_ledger_path: Path | str,
    approval_ledger_path: Path | str | None = None,
) -> dict[str, Any]:
    root = Path(repository_root).resolve()
    if not verify_operator_credential(operator_credential, expected_credential):
        raise PermissionError("valid local operator credential required")

    packet_digest = str(request.get("packet_digest_sha256") or "")
    operator_id = str(request.get("operator_id") or "").strip()
    rationale = str(request.get("rationale") or "").strip()
    expiry = str(request.get("expires_at") or "").strip()
    nonce = str(request.get("nonce") or "").strip()
    account_fingerprint = str(request.get("account_fingerprint") or "").strip()
    if len(packet_digest) != 64 or not operator_id or not rationale or not expiry or len(nonce) < 16 or len(account_fingerprint) < 8:
        raise ValueError("packet digest, account fingerprint, operator, rationale, future expiry, and one-time nonce are required")
    if _parse_utc(expiry) <= datetime.now(timezone.utc):
        raise ValueError("third-stage approval expiry must be in the future")

    packets = _verified_chain(Path(packet_ledger_path), "packet_receipt_sha256")
    matches = [packet for packet in packets if packet.get("packet_digest_sha256") == packet_digest]
    if len(matches) != 1:
        raise ValueError("exactly one verified prepared packet is required")
    packet = matches[0]
    if packet.get("packet_status") != "PREPARED_NOT_EXECUTED" or packet.get("action_type") != "SUBMIT_PROPOSAL":
        raise ValueError("packet is not eligible for Gmail draft preparation")

    second = _verified_chain(Path(second_stage_ledger_path), "approval_receipt_sha256")
    approvals = [approval for approval in second if approval.get("packet_digest_sha256") == packet_digest]
    if len(approvals) != 1 or approvals[0].get("approval_status") != "PREPARED_NOT_EXECUTED":
        raise ValueError("verified second-stage approval is required")
    if approvals[0].get("packet_receipt_sha256") not in {None, packet.get("packet_receipt_sha256")}:
        raise ValueError("second-stage approval is not bound to the verified packet receipt")

    path = _runtime_path(root, approval_ledger_path, "gmail_draft_approvals.jsonl")
    prior = _verified_chain(path, "third_stage_receipt_sha256")
    if any(item.get("packet_digest_sha256") == packet_digest or item.get("nonce") == nonce for item in prior):
        raise ValueError("third-stage approval replay is prohibited")

    payload = _packet_payload(packet)
    if not payload["to"] or not payload["body"]:
        raise ValueError("draft destination and body are required")

    body = {
        "schema_version": "1.0.0",
        "approval_status": "GMAIL_DRAFT_CREATION_AUTHORIZED_ONCE",
        "connector": ALLOWED_CONNECTOR,
        "action_type": ALLOWED_ACTION,
        "account_fingerprint": account_fingerprint,
        "packet_digest_sha256": packet_digest,
        "packet_receipt_sha256": packet.get("packet_receipt_sha256"),
        "second_stage_receipt_sha256": approvals[0].get("approval_receipt_sha256"),
        "destination": payload["to"],
        "payload_digest_sha256": _digest(payload),
        "operator_id": operator_id,
        "rationale": rationale,
        "expires_at": expiry,
        "nonce": nonce,
        "approved_at": _now(),
        "one_time": True,
        "send_authorized": False,
        "external_action_performed": False,
        "canonical_state_mutated": False,
    }
    return _append_chained(path, body, "third_stage_receipt_sha256")


def _execution_record_base(
    *,
    result: str,
    provider: GmailDraftProvider,
    destination: str,
    packet_digest: str,
    third_stage_receipt: str,
    emergency_stop_revision: str,
    idempotency_key: str,
    provider_object_id: str | None,
    provider_verified: bool,
    external_action_performed: bool,
) -> dict[str, Any]:
    return {
        "schema_version": "1.0.0",
        "result": result,
        "provider": ALLOWED_CONNECTOR,
        "account_fingerprint": provider.account_fingerprint,
        "action_type": ALLOWED_ACTION,
        "destination_sha256": sha256(destination.encode("utf-8")).hexdigest(),
        "packet_digest_sha256": packet_digest,
        "third_stage_receipt_sha256": third_stage_receipt,
        "emergency_stop_revision": emergency_stop_revision,
        "idempotency_key": idempotency_key,
        "provider_object_id_sha256": sha256(provider_object_id.encode("utf-8")).hexdigest() if provider_object_id else None,
        "response_timestamp": _now(),
        "provider_verified": provider_verified,
        "send_performed": False,
        "external_action_performed": external_action_performed,
        "external_action_type": "REVERSIBLE_DRAFT_CREATION",
        "canonical_state_mutated": False,
    }


def execute_gmail_draft(
    repository_root: Path | str,
    *,
    third_stage_receipt_sha256: str,
    provider: GmailDraftProvider | None,
    emergency_stop_path: Path | str,
    packet_ledger_path: Path | str,
    approval_ledger_path: Path | str,
    execution_ledger_path: Path | str | None = None,
) -> dict[str, Any]:
    root = Path(repository_root).resolve()
    if provider is None:
        raise ValueError("Gmail draft provider is not configured")
    if not isinstance(provider.account_fingerprint, str) or len(provider.account_fingerprint) < 8:
        raise ValueError("Gmail provider account fingerprint is invalid")

    approvals = _verified_chain(Path(approval_ledger_path), "third_stage_receipt_sha256")
    matches = [approval for approval in approvals if approval.get("third_stage_receipt_sha256") == third_stage_receipt_sha256]
    if len(matches) != 1:
        raise ValueError("exactly one verified third-stage approval is required")
    approval = matches[0]
    if approval.get("connector") != ALLOWED_CONNECTOR or approval.get("action_type") != ALLOWED_ACTION or approval.get("send_authorized") is not False:
        raise ValueError("connector/action allowlist violation")
    if approval.get("account_fingerprint") != provider.account_fingerprint:
        raise ValueError("third-stage approval is not bound to the configured Gmail account")
    if _parse_utc(str(approval.get("expires_at") or "")) <= datetime.now(timezone.utc):
        raise PermissionError("third-stage approval has expired")

    packets = _verified_chain(Path(packet_ledger_path), "packet_receipt_sha256")
    packet_matches = [packet for packet in packets if packet.get("packet_digest_sha256") == approval.get("packet_digest_sha256")]
    if len(packet_matches) != 1:
        raise ValueError("approved packet is unavailable")
    packet = packet_matches[0]
    if packet.get("packet_receipt_sha256") != approval.get("packet_receipt_sha256"):
        raise ValueError("third-stage approval is not bound to the verified packet receipt")

    payload = _packet_payload(packet)
    if not payload["to"] or not payload["body"]:
        raise ValueError("draft destination and body are required")
    if not hmac.compare_digest(_digest(payload), str(approval.get("payload_digest_sha256") or "")):
        raise ValueError("third-stage approval payload binding is invalid")

    path = _runtime_path(root, execution_ledger_path, "gmail_draft_execution_receipts.jsonl")
    prior = _verified_chain(path, "execution_receipt_sha256")
    idempotency_key = _digest({
        "approval": third_stage_receipt_sha256,
        "packet": packet.get("packet_digest_sha256"),
        "action": ALLOWED_ACTION,
        "account": provider.account_fingerprint,
    })
    existing = [record for record in prior if record.get("idempotency_key") == idempotency_key]
    if existing:
        terminal = [record for record in existing if record.get("result") in {TERMINAL_STATE, UNCERTAIN_STATE}]
        return terminal[-1] if terminal else existing[-1]

    stop = load_emergency_stop(emergency_stop_path)
    if stop.enabled:
        raise PermissionError(f"emergency stop enabled: {stop.reason}")

    reservation = _execution_record_base(
        result=RESERVED_STATE,
        provider=provider,
        destination=payload["to"],
        packet_digest=str(packet.get("packet_digest_sha256") or ""),
        third_stage_receipt=third_stage_receipt_sha256,
        emergency_stop_revision=stop.revision,
        idempotency_key=idempotency_key,
        provider_object_id=None,
        provider_verified=False,
        external_action_performed=False,
    )
    reservation["request_timestamp"] = _now()
    _append_chained(path, reservation, "execution_receipt_sha256")

    # Re-read immediately before the only external provider call.
    stop = load_emergency_stop(emergency_stop_path)
    if stop.enabled:
        uncertain = _execution_record_base(
            result=UNCERTAIN_STATE,
            provider=provider,
            destination=payload["to"],
            packet_digest=str(packet.get("packet_digest_sha256") or ""),
            third_stage_receipt=third_stage_receipt_sha256,
            emergency_stop_revision=stop.revision,
            idempotency_key=idempotency_key,
            provider_object_id=None,
            provider_verified=False,
            external_action_performed=False,
        )
        uncertain["uncertainty_reason"] = "EMERGENCY_STOP_CHANGED_AFTER_RESERVATION"
        return _append_chained(path, uncertain, "execution_receipt_sha256")

    draft_id: str | None = None
    try:
        created = dict(provider.create_draft(
            to=payload["to"],
            subject=payload["subject"],
            body=payload["body"],
            idempotency_key=idempotency_key,
        ))
        draft_id = str(created.get("draft_id") or "")
        if not draft_id:
            raise RuntimeError("provider response did not include a draft identifier")
        fetched = dict(provider.get_draft(draft_id))
        observed = {
            "to": str(fetched.get("to") or ""),
            "subject": str(fetched.get("subject") or ""),
            "body": str(fetched.get("body") or ""),
        }
        verified = hmac.compare_digest(_digest(payload), _digest(observed)) and fetched.get("sent") is False
        if not verified:
            raise RuntimeError("created Gmail draft could not be verified")
    except Exception as exc:
        uncertain = _execution_record_base(
            result=UNCERTAIN_STATE,
            provider=provider,
            destination=payload["to"],
            packet_digest=str(packet.get("packet_digest_sha256") or ""),
            third_stage_receipt=third_stage_receipt_sha256,
            emergency_stop_revision=stop.revision,
            idempotency_key=idempotency_key,
            provider_object_id=draft_id,
            provider_verified=False,
            external_action_performed=True,
        )
        uncertain["uncertainty_reason"] = type(exc).__name__
        return _append_chained(path, uncertain, "execution_receipt_sha256")

    receipt = _execution_record_base(
        result=TERMINAL_STATE,
        provider=provider,
        destination=payload["to"],
        packet_digest=str(packet.get("packet_digest_sha256") or ""),
        third_stage_receipt=third_stage_receipt_sha256,
        emergency_stop_revision=stop.revision,
        idempotency_key=idempotency_key,
        provider_object_id=draft_id,
        provider_verified=True,
        external_action_performed=True,
    )
    receipt["request_timestamp"] = created.get("request_timestamp") or reservation["request_timestamp"]
    return _append_chained(path, receipt, "execution_receipt_sha256")


def build_gateway_projection(
    repository_root: Path | str,
    *,
    approval_ledger_path: Path | str | None = None,
    execution_ledger_path: Path | str | None = None,
) -> dict[str, Any]:
    root = Path(repository_root).resolve()
    approvals = _verified_chain(
        _runtime_path(root, approval_ledger_path, "gmail_draft_approvals.jsonl"),
        "third_stage_receipt_sha256",
    )
    receipts = _verified_chain(
        _runtime_path(root, execution_ledger_path, "gmail_draft_execution_receipts.jsonl"),
        "execution_receipt_sha256",
    )
    return {
        "schema_version": "1.0.0",
        "mode": "GOVERNED_SINGLE_ACTION_GATEWAY",
        "allowed_connector": ALLOWED_CONNECTOR,
        "allowed_action": ALLOWED_ACTION,
        "third_stage_approvals": approvals,
        "execution_receipts": receipts,
        "terminal_state": TERMINAL_STATE,
        "send_capability_present": False,
        "other_external_actions_present": False,
        "canonical_state_mutated": False,
    }
