"""Governed execution preparation for Ω Mission OS Increment 7.

This module consumes verified first-stage authorization receipts, compiles
immutable execution packets, performs deterministic dry runs, and records a
separate one-time approval. It never invokes an external connector or performs
the prepared action.
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
    for line in path.read_text(encoding="utf-8").splitlines():
        value = json.loads(line)
        if not isinstance(value, dict):
            raise ValueError("execution preparation ledger contains a non-object record")
        records.append(value)
    return records


def _append_jsonl(path: Path, value: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(dict(value), sort_keys=True, ensure_ascii=False) + "\n")


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
    proposals = _proposal_map(root)
    proposal = proposals.get(proposal_id)
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
    checks = {
        "revision_matches": proposal.get("exact_revision") == authorization.get("exact_revision"),
        "counterparty_bound": bool(proposal.get("counterparty")),
        "channel_bound": bool(proposal.get("submission_channel")),
        "scope_present": bool(proposal.get("scope") or proposal.get("deliverables")),
        "price_classified": proposal.get("price_classification") in {"INTERNAL_LIST_PRICE", "SOURCE_EVIDENCED"},
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

    packet_body = {
        "schema_version": "1.0.0",
        "packet_status": "PREPARED_NOT_EXECUTED",
        "proposal_id": proposal_id,
        "proposal_revision": proposal.get("exact_revision"),
        "authorization_receipt_sha256": authorization.get("decision_receipt_sha256"),
        "counterparty": proposal.get("counterparty"),
        "submission_channel": proposal.get("submission_channel"),
        "action_type": "SUBMIT_PROPOSAL",
        "message_body": proposal.get("message_body") or proposal.get("proposal_text") or "",
        "attachments": proposal.get("attachments") or [],
        "scope": proposal.get("scope") or proposal.get("deliverables") or [],
        "price": proposal.get("price"),
        "price_classification": proposal.get("price_classification"),
        "preflight": preflight,
        "compiled_at": _utc_now(),
        "external_action_authorized": False,
        "external_action_performed": False,
        "canonical_state_mutated": False,
    }
    packet = dict(packet_body)
    packet["packet_digest_sha256"] = _digest(packet_body)
    packet["dry_run"] = _dry_run_adapter(packet_body)

    path = _runtime_path(root, packet_ledger_path, "execution_packets.jsonl")
    existing = _read_jsonl(path)
    if any(item.get("packet_digest_sha256") == packet["packet_digest_sha256"] for item in existing):
        raise ValueError("duplicate execution packet compilation is prohibited")
    _append_jsonl(path, packet)
    return packet


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
    packets = _read_jsonl(packet_path)
    matches = [item for item in packets if item.get("packet_digest_sha256") == packet_digest]
    if len(matches) != 1:
        raise ValueError("exactly one immutable execution packet must match the requested digest")
    packet = matches[0]
    if packet.get("packet_status") != "PREPARED_NOT_EXECUTED" or packet.get("external_action_performed") is not False:
        raise ValueError("execution packet is not eligible for second-stage approval")

    approval_path = _runtime_path(root, approval_ledger_path, "execution_approvals.jsonl")
    prior = _read_jsonl(approval_path)
    if any(item.get("packet_digest_sha256") == packet_digest for item in prior):
        raise ValueError("one-time execution packet approval has already been consumed")

    body = {
        "schema_version": "1.0.0",
        "approval_status": "PREPARED_NOT_EXECUTED",
        "packet_digest_sha256": packet_digest,
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
    approval = dict(body)
    approval["approval_receipt_sha256"] = _digest(body)
    _append_jsonl(approval_path, approval)
    return approval


def build_execution_preparation_projection(
    repository_root: Path | str,
    *,
    packet_ledger_path: Path | str | None = None,
    approval_ledger_path: Path | str | None = None,
) -> dict[str, Any]:
    root = Path(repository_root).resolve()
    packets = _read_jsonl(_runtime_path(root, packet_ledger_path, "execution_packets.jsonl"))
    approvals = _read_jsonl(_runtime_path(root, approval_ledger_path, "execution_approvals.jsonl"))
    return {
        "schema_version": "1.0.0",
        "mode": "EXECUTION_PREPARATION_ONLY",
        "packets": packets,
        "second_stage_approvals": approvals,
        "terminal_state": "PREPARED_NOT_EXECUTED",
        "external_action_authorized": False,
        "external_action_performed": False,
        "canonical_state_mutated": False,
    }
