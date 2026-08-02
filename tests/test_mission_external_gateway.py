from __future__ import annotations

from datetime import datetime, timedelta, timezone
from hashlib import sha256
import json
from pathlib import Path

import pytest

from src.mission_os.external_gateway import (
    build_gateway_projection,
    create_third_stage_approval,
    execute_gmail_draft,
    load_emergency_stop,
)


def _digest(value: dict) -> str:
    return sha256(json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode()).hexdigest()


def _append(path: Path, body: dict, receipt_field: str) -> dict:
    previous = None
    if path.exists():
        records = [json.loads(line) for line in path.read_text().splitlines() if line]
        previous = records[-1][receipt_field]
    value = dict(body)
    value["previous_receipt_sha256"] = previous
    value[receipt_field] = _digest(value)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(value, sort_keys=True) + "\n")
    return value


def _credential() -> str:
    return "".join(["local", "-operator", "-credential"])


def _fixtures(tmp_path: Path) -> tuple[Path, Path, dict]:
    packets = tmp_path / ".runtime/packets.jsonl"
    seconds = tmp_path / ".runtime/seconds.jsonl"
    packet_body = {
        "schema_version": "1.0.0",
        "packet_status": "PREPARED_NOT_EXECUTED",
        "proposal_id": "proposal-1",
        "proposal_revision": "a" * 64,
        "authorization_receipt_sha256": "b" * 64,
        "counterparty": "Example Client",
        "submission_channel": "client@example.test",
        "action_type": "SUBMIT_PROPOSAL",
        "title": "Governed workflow proposal",
        "message_body": "Attached is the governed workflow proposal.",
        "dry_run": {"status": "SIMULATED_NO_EXTERNAL_CALL", "external_call_performed": False},
        "external_action_authorized": False,
        "external_action_performed": False,
        "canonical_state_mutated": False,
    }
    packet_body["packet_digest_sha256"] = _digest(packet_body)
    packet = _append(packets, packet_body, "packet_receipt_sha256")
    second = {
        "schema_version": "1.0.0",
        "approval_status": "PREPARED_NOT_EXECUTED",
        "packet_digest_sha256": packet["packet_digest_sha256"],
        "proposal_id": "proposal-1",
        "external_action_authorized": False,
        "external_action_performed": False,
        "canonical_state_mutated": False,
    }
    _append(seconds, second, "approval_receipt_sha256")
    return packets, seconds, packet


class FakeGmailDraftProvider:
    account_fingerprint = "acct-sha256-test"

    def __init__(self) -> None:
        self.create_calls = 0
        self._drafts: dict[str, dict] = {}

    def create_draft(self, *, to: str, subject: str, body: str, idempotency_key: str) -> dict:
        self.create_calls += 1
        draft_id = f"draft-{idempotency_key[:12]}"
        self._drafts[draft_id] = {"to": to, "subject": subject, "body": body, "sent": False}
        return {"draft_id": draft_id, "request_timestamp": "2026-08-02T21:00:00Z"}

    def get_draft(self, draft_id: str) -> dict:
        return dict(self._drafts[draft_id])


def _approval(tmp_path: Path, packets: Path, seconds: Path, packet: dict) -> tuple[Path, dict]:
    approvals = tmp_path / ".runtime/third.jsonl"
    value = create_third_stage_approval(
        tmp_path,
        {
            "packet_digest_sha256": packet["packet_digest_sha256"],
            "operator_id": "Justice",
            "rationale": "Create the exact reviewed Gmail draft only.",
            "expires_at": (datetime.now(timezone.utc) + timedelta(hours=1)).isoformat().replace("+00:00", "Z"),
            "nonce": "nonce-1234567890-unique",
        },
        operator_credential=_credential(),
        expected_credential=_credential(),
        packet_ledger_path=packets,
        second_stage_ledger_path=seconds,
        approval_ledger_path=approvals,
    )
    return approvals, value


def test_third_stage_approval_is_exact_one_time_and_never_authorizes_send(tmp_path: Path) -> None:
    packets, seconds, packet = _fixtures(tmp_path)
    approvals, approval = _approval(tmp_path, packets, seconds, packet)
    assert approval["connector"] == "GMAIL"
    assert approval["action_type"] == "CREATE_DRAFT"
    assert approval["send_authorized"] is False
    with pytest.raises(ValueError, match="replay"):
        _approval(tmp_path, packets, seconds, packet)
    assert approvals.exists()


def test_emergency_stop_fails_closed(tmp_path: Path) -> None:
    packets, seconds, packet = _fixtures(tmp_path)
    approvals, approval = _approval(tmp_path, packets, seconds, packet)
    stop = tmp_path / "stop.json"
    stop.write_text(json.dumps({"schema_version": "1.0.0", "enabled": True, "revision": "LOCKED-0001", "reason": "test"}))
    with pytest.raises(PermissionError, match="emergency stop"):
        execute_gmail_draft(
            tmp_path,
            third_stage_receipt_sha256=approval["third_stage_receipt_sha256"],
            provider=FakeGmailDraftProvider(),
            emergency_stop_path=stop,
            packet_ledger_path=packets,
            approval_ledger_path=approvals,
        )


def test_create_verify_and_idempotently_return_gmail_draft_receipt(tmp_path: Path) -> None:
    packets, seconds, packet = _fixtures(tmp_path)
    approvals, approval = _approval(tmp_path, packets, seconds, packet)
    stop = tmp_path / "stop.json"
    stop.write_text(json.dumps({"schema_version": "1.0.0", "enabled": False, "revision": "OPEN-00000001", "reason": "authorized test"}))
    executions = tmp_path / ".runtime/executions.jsonl"
    provider = FakeGmailDraftProvider()
    first = execute_gmail_draft(
        tmp_path,
        third_stage_receipt_sha256=approval["third_stage_receipt_sha256"],
        provider=provider,
        emergency_stop_path=stop,
        packet_ledger_path=packets,
        approval_ledger_path=approvals,
        execution_ledger_path=executions,
    )
    second = execute_gmail_draft(
        tmp_path,
        third_stage_receipt_sha256=approval["third_stage_receipt_sha256"],
        provider=provider,
        emergency_stop_path=stop,
        packet_ledger_path=packets,
        approval_ledger_path=approvals,
        execution_ledger_path=executions,
    )
    assert first == second
    assert provider.create_calls == 1
    assert first["result"] == "DRAFT_CREATED_NOT_SENT"
    assert first["provider_verified"] is True
    assert first["send_performed"] is False
    assert first["external_action_performed"] is True
    assert "client@example.test" not in json.dumps(first)


def test_tampered_execution_receipt_fails_closed(tmp_path: Path) -> None:
    packets, seconds, packet = _fixtures(tmp_path)
    approvals, approval = _approval(tmp_path, packets, seconds, packet)
    stop = tmp_path / "stop.json"
    stop.write_text(json.dumps({"schema_version": "1.0.0", "enabled": False, "revision": "OPEN-00000001", "reason": "authorized test"}))
    executions = tmp_path / ".runtime/executions.jsonl"
    execute_gmail_draft(tmp_path, third_stage_receipt_sha256=approval["third_stage_receipt_sha256"], provider=FakeGmailDraftProvider(), emergency_stop_path=stop, packet_ledger_path=packets, approval_ledger_path=approvals, execution_ledger_path=executions)
    record = json.loads(executions.read_text())
    record["provider_verified"] = False
    executions.write_text(json.dumps(record) + "\n")
    with pytest.raises(ValueError, match="integrity"):
        build_gateway_projection(tmp_path, approval_ledger_path=approvals, execution_ledger_path=executions)


def test_credentials_and_provider_secrets_are_not_persisted(tmp_path: Path) -> None:
    packets, seconds, packet = _fixtures(tmp_path)
    approvals, approval = _approval(tmp_path, packets, seconds, packet)
    combined = approvals.read_text() + json.dumps(approval)
    assert _credential() not in combined
    assert "access_token" not in combined
    assert "refresh_token" not in combined


def test_missing_or_invalid_emergency_stop_is_blocking(tmp_path: Path) -> None:
    with pytest.raises(ValueError):
        load_emergency_stop(tmp_path / "missing.json")
