"""Governed execution preparation for Ω Mission OS Increment 7.

Consumes a verified first-stage authorization, compiles a deterministic
preparation packet, performs a no-network dry run, and records a separate
one-time second-stage approval. No function executes the prepared action.
"""

from __future__ import annotations

from datetime import datetime, timezone
from hashlib import sha256
import json
from pathlib import Path
from typing import Any, Mapping

from src.mission_os.activation import build_activation_projection
from src.mission_os.decisions import read_operator_decisions, verify_operator_credential


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _digest(value: Mapping[str, Any]) -> str:
    payload = json.dumps(dict(value), sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return sha256(payload.encode("utf-8")).hexdigest()


def _runtime_path(root: Path, configured: Path | str | None, filename: str) -> Path:
    path = Path(configured) if configured is not None else root / ".aigc" / "mission_os" / filename
    path = path.resolve()
    forbidden = [root / "data", root / "memory", root / "governance", root / "config"]
    if any(path == item.resolve() or item.resolve() in path.parents for item in forbidden):
        raise ValueError("execution preparation records must remain outside canonical state roots")
    return path


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.is_file():
        return []
    records: list[dict[str, Any]] = []
    for line_number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        try:
            value = json.loads(line)
        except json.JSONDecodeError as exc:
            raise ValueError(f"execution ledger contains invalid JSON at line {line_number}") from exc
        if not isinstance(value, dict):
            raise ValueError(f"execution ledger contains a non-object record at line {line_number}")
        records.append(value)
    return records


def _verify_chain(records: list[dict[str, Any]], digest_field: str) -> None:
    previous: str | None = None
    for index, record in enumerate(records):
        claimed = record.get(digest_field)
        if not isinstance(claimed, str) or len(claimed) != 64:
            raise ValueError(f"execution ledger receipt {index} lacks a valid digest")
        if record.get("previous_receipt_sha256") != previous:
            raise ValueError(f"execution ledger chain discontinuity at receipt {index}")
        body = {key: value for key, value in record.items() if key != digest_field}
        if _digest(body) != claimed:
            raise ValueError(f"execution ledger digest mismatch at receipt {index}")
        previous = claimed


def _load_verified(path: Path, digest_field: str) -> list[dict[str, Any]]:
    records = _read_jsonl(path)
    _verify_chain(records, digest_field)
    return records


def _append_chained(path: Path, body: Mapping[str, Any], digest_field: str) -> dict[str, Any]:
    existing = _load_verified(path, digest_field)
    record = dict(body)
    record["previous_receipt_sha256"] = existing[-1][digest_field] if existing else None
    record[digest_field] = _digest(record)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(record, sort_keys=True, ensure_ascii=False) + "\n")
    return record


def _proposal_map(root: Path) -> dict[str, dict[str, Any]]:
    projection = build_activation_projection(root)
    return {
        str(item.get("proposal_id")): dict(item)
        for item in projection.get("internal_proposal_packets", [])
        if isinstance(item, Mapping)
    }


def consume_authorization(
    repository_root: Path | str,
    proposal_id: str,
    *,
    decision_ledger_path: Path | str | None = None,
) -> dict[str, Any]:
    root = Path(repository_root).resolve()
    ledger = read_operator_decisions(root, ledger_path=decision_ledger_path)
    if ledger.get("integrity_status") != "VERIFIED":
        raise ValueError("authorization ledger integrity is not verified")

    matching = [
        item for item in ledger.get("records", [])
        if item.get("proposal_id") == proposal_id
        and item.get("decision_status") == "AUTHORIZED_NOT_EXECUTED"
        and item.get("external_action_authorized") is True
        and item.get("external_action_performed") is False
    ]
    if len(matching) != 1:
        raise ValueError("exactly one valid unexecuted authorization receipt is required")

    authorization = dict(matching[0])
    proposal = _proposal_map(root).get(proposal_id)
    if proposal is None:
        raise ValueError("authorized proposal is no longer present")
    if proposal.get("exact_revision") != authorization.get("exact_revision"):
        raise ValueError("authorization is stale relative to the current proposal revision")
    if not authorization.get("binding_complete"):
        raise ValueError("authorization binding is incomplete")
    if not authorization.get("counterparty") or not authorization.get("submission_channel"):
        raise ValueError("authorization lacks counterparty or submission channel")
    return {"authorization": authorization, "proposal": proposal}


def run_preflight(proposal: Mapping[str, Any], authorization: Mapping[str, Any]) -> dict[str, Any]:
    price = proposal.get("proposed_list_price_cad")
    classification = proposal.get("price_classification")
    checks = {
        "revision_matches": proposal.get("exact_revision") == authorization.get("exact_revision"),
        "counterparty_matches": proposal.get("counterparty") == authorization.get("counterparty"),
        "channel_matches": proposal.get("submission_channel") == authorization.get("submission_channel"),
        "counterparty_bound": bool(proposal.get("counterparty")),
        "channel_bound": bool(proposal.get("submission_channel")),
        "scope_present": bool(proposal.get("scope") or proposal.get("deliverables")),
        "price_present": isinstance(price, (int, float)) and not isinstance(price, bool) and price >= 0,
        "price_classified": classification in {
            "INTERNAL_OFFER_LIST_PRICE_NOT_COUNTERPARTY_BUDGET",
            "SOURCE_EVIDENCED",
        },
        "external_action_not_performed": authorization.get("external_action_performed") is False,
        "canonical_state_not_mutated": authorization.get("canonical_state_mutated") is False,
    }
    blockers = [name for name, passed in checks.items() if not passed]
    return {
        "status": "PASS" if not blockers else "BLOCKED",
        "checks": checks,
        "blockers": blockers,
        "evaluated_at": _utc_now(),
    }


def _dry_run_adapter(packet_body: Mapping[str, Any]) -> dict[str, Any]:
    channel = str(packet_body.get("submission_channel") or "")
    if channel.startswith("mailto:") or "@" in channel:
        adapter = "EMAIL_DRY_RUN"
    elif channel.startswith("http://") or channel.startswith("https://"):
        adapter = "WEB_FORM_DRY_RUN"
    else:
        adapter = "GENERIC_CONNECTOR_DRY_RUN"
    return {
        "adapter": adapter,
        "status": "SIMULATED_NO_EXTERNAL_CALL",
        "destination": channel,
        "expected_side_effects": ["External submission would occur only in a future separately governed increment."],
        "external_call_performed": False,
        "provider_response": None,
    }


def compile_execution_packet(
    repository_root: Path | str,
    proposal_id: str,
    *,
    decision_ledger_path: Path | str | None = None,
    packet_ledger_path: Path | str | None = None,
) -> dict[str, Any]:
    root = Path(repository_root).resolve()
    consumed = consume_authorization(root, proposal_id, decision_ledger_path=decision_ledger_path)
    proposal = consumed["proposal"]
    authorization = consumed["authorization"]
    preflight = run_preflight(proposal, authorization)
    if preflight["status"] != "PASS":
        raise ValueError(f"execution preflight blocked: {preflight['blockers']}")

    path = _runtime_path(root, packet_ledger_path, "execution_packets.jsonl")
    existing = _load_verified(path, "packet_receipt_sha256")
    authorization_digest = authorization.get("decision_receipt_sha256")
    if any(
        item.get("proposal_id") == proposal_id
        and item.get("proposal_revision") == proposal.get("exact_revision")
        and item.get("authorization_receipt_sha256") == authorization_digest
        for item in existing
    ):
        raise ValueError("this exact authorization has already been compiled")

    core = {
        "schema_version": "1.0.0",
        "packet_status": "PREPARED_NOT_EXECUTED",
        "proposal_id": proposal_id,
        "proposal_revision": proposal.get("exact_revision"),
        "authorization_receipt_sha256": authorization_digest,
        "counterparty": proposal.get("counterparty"),
        "submission_channel": proposal.get("submission_channel"),
        "action_type": "SUBMIT_PROPOSAL",
        "message_body": proposal.get("message_body") or proposal.get("proposal_text") or "",
        "attachments": proposal.get("attachments") or [],
        "scope": proposal.get("scope") or proposal.get("deliverables") or [],
        "price": proposal.get("proposed_list_price_cad"),
        "price_classification": proposal.get("price_classification"),
        "preflight": preflight,
        "compiled_at": _utc_now(),
        "external_action_authorized": False,
        "external_action_performed": False,
        "canonical_state_mutated": False,
    }
    core["dry_run"] = _dry_run_adapter(core)
    core["packet_digest_sha256"] = _digest(core)
    return _append_chained(path, core, "packet_receipt_sha256")


def approve_execution_packet(
    repository_root: Path | str,
    request: Mapping[str, Any],
    *,
    operator_credential: str | None,
    expected_credential: str | None = None,
    packet_ledger_path: Path | str | None = None,
    approval_ledger_path: Path | str | None = None,
) -> dict[str, Any]:
    root = Path(repository_root).resolve()
    if not verify_operator_credential(operator_credential, expected_credential):
        raise PermissionError("valid local operator credential required")

    packet_digest = str(request.get("packet_digest_sha256") or "")
    operator_id = str(request.get("operator_id") or "").strip()
    rationale = str(request.get("rationale") or "").strip()
    if len(packet_digest) != 64 or not operator_id or not rationale:
        raise ValueError("packet_digest_sha256, operator_id, and rationale are required")

    packet_path = _runtime_path(root, packet_ledger_path, "execution_packets.jsonl")
    packets = _load_verified(packet_path, "packet_receipt_sha256")
    matches = [item for item in packets if item.get("packet_digest_sha256") == packet_digest]
    if len(matches) != 1:
        raise ValueError("exactly one verified execution packet must match the requested digest")
    packet = matches[0]
    packet_body = {
        key: value for key, value in packet.items()
        if key not in {"packet_receipt_sha256", "previous_receipt_sha256", "packet_digest_sha256"}
    }
    if _digest(packet_body) != packet_digest:
        raise ValueError("execution packet content does not match its immutable packet digest")
    if packet.get("packet_status") != "PREPARED_NOT_EXECUTED" or packet.get("external_action_performed") is not False:
        raise ValueError("execution packet is not eligible for second-stage approval")

    approval_path = _runtime_path(root, approval_ledger_path, "execution_approvals.jsonl")
    prior = _load_verified(approval_path, "approval_receipt_sha256")
    if any(item.get("packet_digest_sha256") == packet_digest for item in prior):
        raise ValueError("one-time execution packet approval has already been consumed")

    body = {
        "schema_version": "1.0.0",
        "approval_status": "PREPARED_NOT_EXECUTED",
        "packet_digest_sha256": packet_digest,
        "packet_receipt_sha256": packet.get("packet_receipt_sha256"),
        "proposal_id": packet.get("proposal_id"),
        "proposal_revision": packet.get("proposal_revision"),
        "counterparty": packet.get("counterparty"),
        "submission_channel": packet.get("submission_channel"),
        "operator_id": operator_id,
        "rationale": rationale,
        "approved_at": _utc_now(),
        "one_time": True,
        "external_action_authorized": False,
        "external_action_performed": False,
        "canonical_state_mutated": False,
    }
    return _append_chained(approval_path, body, "approval_receipt_sha256")


def build_execution_preparation_projection(
    repository_root: Path | str,
    *,
    packet_ledger_path: Path | str | None = None,
    approval_ledger_path: Path | str | None = None,
) -> dict[str, Any]:
    root = Path(repository_root).resolve()
    packets = _load_verified(
        _runtime_path(root, packet_ledger_path, "execution_packets.jsonl"),
        "packet_receipt_sha256",
    )
    approvals = _load_verified(
        _runtime_path(root, approval_ledger_path, "execution_approvals.jsonl"),
        "approval_receipt_sha256",
    )
    return {
        "schema_version": "1.0.0",
        "mode": "EXECUTION_PREPARATION_ONLY",
        "integrity_status": "VERIFIED",
        "packets": packets,
        "second_stage_approvals": approvals,
        "terminal_state": "PREPARED_NOT_EXECUTED",
        "external_action_authorized": False,
        "external_action_performed": False,
        "canonical_state_mutated": False,
    }
