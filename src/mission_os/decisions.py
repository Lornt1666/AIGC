"""Human-only proposal decisions for Ω Mission OS Increment 6.

This module records local operator decisions. It never performs the authorized
external action and never mutates canonical Quest, phase, finance, or evidence
state.
"""

from __future__ import annotations

from datetime import datetime, timezone
from hashlib import sha256
import hmac
import json
import os
from pathlib import Path
from typing import Any, Mapping

from src.mission_os.activation import build_activation_projection

ALLOWED_DECISIONS = {"REJECT", "REQUEST_REVISION", "AUTHORIZE_EXACT_PROPOSAL"}


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _canonical_digest(value: Mapping[str, Any]) -> str:
    payload = json.dumps(dict(value), sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return sha256(payload.encode("utf-8")).hexdigest()


def _decision_path(root: Path, configured: Path | str | None = None) -> Path:
    path = Path(configured) if configured is not None else root / ".aigc" / "mission_os" / "operator_decisions.jsonl"
    path = path.resolve()
    canonical_roots = [root / "data", root / "memory", root / "governance", root / "config"]
    if any(path == candidate.resolve() or candidate.resolve() in path.parents for candidate in canonical_roots):
        raise ValueError("decision ledger must remain outside canonical repository state")
    return path


def verify_operator_credential(provided: str | None, expected: str | None = None) -> bool:
    expected_value = expected if expected is not None else os.getenv("MISSION_OS_OPERATOR_TOKEN")
    if not expected_value or not provided:
        return False
    return hmac.compare_digest(provided, expected_value)


def _find_proposal(root: Path, proposal_id: str) -> tuple[dict[str, Any], dict[str, Any]]:
    projection = build_activation_projection(root)
    proposals = {
        str(item.get("proposal_id")): item
        for item in projection.get("internal_proposal_packets", [])
        if isinstance(item, Mapping)
    }
    approvals = {
        str(item.get("proposal_id")): item
        for item in projection.get("exact_action_approval_queue", [])
        if isinstance(item, Mapping)
    }
    if proposal_id not in proposals:
        raise ValueError("proposal not found in current activation projection")
    return dict(proposals[proposal_id]), dict(approvals.get(proposal_id, {}))


def _read_verified_ledger(path: Path) -> tuple[list[dict[str, Any]], int, str]:
    records: list[dict[str, Any]] = []
    invalid_lines = 0
    expected_previous: str | None = None
    if not path.is_file():
        return records, invalid_lines, "VERIFIED"

    for line in path.read_text(encoding="utf-8").splitlines():
        try:
            value = json.loads(line)
        except json.JSONDecodeError:
            invalid_lines += 1
            break
        if not isinstance(value, dict):
            invalid_lines += 1
            break

        receipt = value.get("decision_receipt_sha256")
        body = {key: item for key, item in value.items() if key != "decision_receipt_sha256"}
        if not isinstance(receipt, str) or _canonical_digest(body) != receipt:
            invalid_lines += 1
            break
        if body.get("previous_receipt_sha256") != expected_previous:
            invalid_lines += 1
            break

        records.append(value)
        expected_previous = receipt

    status = "VERIFIED" if invalid_lines == 0 else "INTEGRITY_FAILURE"
    return records, invalid_lines, status


def record_operator_decision(
    repository_root: Path | str,
    request: Mapping[str, Any],
    *,
    operator_credential: str | None,
    expected_credential: str | None = None,
    ledger_path: Path | str | None = None,
) -> dict[str, Any]:
    root = Path(repository_root).resolve()
    if not verify_operator_credential(operator_credential, expected_credential):
        raise PermissionError("valid local operator credential required")

    decision = str(request.get("decision") or "").upper()
    if decision not in ALLOWED_DECISIONS:
        raise ValueError("unsupported decision")
    proposal_id = str(request.get("proposal_id") or "")
    exact_revision = str(request.get("exact_revision") or "")
    operator_id = str(request.get("operator_id") or "").strip()
    rationale = str(request.get("rationale") or "").strip()
    if not proposal_id or not exact_revision or not operator_id or not rationale:
        raise ValueError("proposal_id, exact_revision, operator_id, and rationale are required")

    proposal, approval = _find_proposal(root, proposal_id)
    if proposal.get("exact_revision") != exact_revision:
        raise ValueError("proposal revision is stale or mismatched")

    binding_complete = approval.get("binding_complete") is True
    approval_status = str(approval.get("status") or "")
    if decision == "AUTHORIZE_EXACT_PROPOSAL":
        if not binding_complete or approval_status == "BLOCKED_BINDING_INCOMPLETE":
            raise ValueError("authorization prohibited: proposal binding is incomplete")

    requested_changes = request.get("requested_changes")
    if decision == "REQUEST_REVISION":
        if not isinstance(requested_changes, list) or not requested_changes:
            raise ValueError("requested_changes are required for revision requests")
    elif requested_changes not in (None, []):
        raise ValueError("requested_changes are only valid for revision requests")

    path = _decision_path(root, ledger_path)
    existing_records, invalid_lines, integrity_status = _read_verified_ledger(path)
    if invalid_lines or integrity_status != "VERIFIED":
        raise ValueError("decision ledger integrity verification failed; append prohibited")
    previous_receipt = existing_records[-1]["decision_receipt_sha256"] if existing_records else None

    recorded_status = {
        "REJECT": "REJECTED",
        "REQUEST_REVISION": "REVISION_REQUESTED",
        "AUTHORIZE_EXACT_PROPOSAL": "AUTHORIZED_NOT_EXECUTED",
    }[decision]
    event_body = {
        "schema_version": "1.1.0",
        "decision": decision,
        "decision_status": recorded_status,
        "proposal_id": proposal_id,
        "exact_revision": exact_revision,
        "operator_id": operator_id,
        "rationale": rationale,
        "requested_changes": requested_changes or [],
        "counterparty": proposal.get("counterparty"),
        "submission_channel": proposal.get("submission_channel"),
        "binding_complete": binding_complete,
        "decided_at": _utc_now(),
        "previous_receipt_sha256": previous_receipt,
        "external_action_authorized": decision == "AUTHORIZE_EXACT_PROPOSAL",
        "external_action_performed": False,
        "canonical_state_mutated": False,
    }
    event = dict(event_body)
    event["decision_receipt_sha256"] = _canonical_digest(event_body)

    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(event, sort_keys=True, ensure_ascii=False) + "\n")
    return event


def read_operator_decisions(
    repository_root: Path | str,
    *,
    ledger_path: Path | str | None = None,
) -> dict[str, Any]:
    root = Path(repository_root).resolve()
    path = _decision_path(root, ledger_path)
    records, invalid_lines, integrity_status = _read_verified_ledger(path)
    return {
        "schema_version": "1.1.0",
        "mode": "LOCAL_OPERATOR_DECISION_LEDGER",
        "records": records,
        "invalid_lines": invalid_lines,
        "integrity_status": integrity_status,
        "external_action_performed": False,
        "canonical_state_mutated": False,
    }
