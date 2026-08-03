from __future__ import annotations

from datetime import datetime, timedelta, timezone
from hashlib import sha256
import json
from pathlib import Path

import pytest

from src.mission_os.connector_adapters import GovernedGmailKernelAdapter, GovernedGitHubKernelAdapter
from src.mission_os.connector_kernel import (
    AppendOnlyEvidenceLedger, ApprovalRecord, ConnectorKernel,
    ExecutionPacket, KernelPolicy,
)


def future() -> str:
    return (datetime.now(timezone.utc) + timedelta(minutes=10)).isoformat()


def idem(value: str) -> str:
    return sha256(value.encode()).hexdigest()


class ApprovalAuthority:
    def __init__(self) -> None:
        self.allowed: set[str] = set()

    def authorize(self, approval: ApprovalRecord) -> None:
        self.allowed.add(approval.approval_sha256)

    def verify(self, approval: ApprovalRecord, packet: ExecutionPacket) -> bool:
        return approval.approval_sha256 in self.allowed and approval.packet_sha256 == packet.packet_sha256


class GmailProvider:
    def health(self):
        return {"status": "HEALTHY_DRAFT_ONLY", "identity": {"email": "private@example.test", "access_token": "secret"}}

    def create_draft(self, *, to, subject, body, idempotency_key):
        return {"draft_id": "draft-1"}

    def get_draft(self, draft_id):
        return {"to": "self@example.test", "subject": "subject", "body": "body", "sent": False}


class GitHubProvider:
    def repository_health(self):
        return {"status": "HEALTHY_READ_ONLY"}

    def read_state(self, query):
        return {"head_sha": "a" * 40, "query": dict(query)}


def packet(connector: str, capability: str, payload: dict, suffix: str = "1") -> ExecutionPacket:
    return ExecutionPacket.compile(
        connector_id=connector,
        capability=capability,
        payload=payload,
        idempotency_key=idem("idempotency-" + suffix),
        approval_id="approval-" + suffix,
        approval_expires_at=future(),
        policy_revision="POLICY-0001",
    )


def approval(value: ExecutionPacket, authority: ApprovalAuthority) -> ApprovalRecord:
    record = ApprovalRecord.compile(
        approval_id=value.approval_id,
        packet_sha256=value.packet_sha256,
        connector_id=value.connector_id,
        capability=value.capability,
        expires_at=value.approval_expires_at,
        authority_id="human-authority-1",
    )
    authority.authorize(record)
    return record


def unlock(stop: Path, value: ExecutionPacket) -> None:
    stop.write_text(json.dumps({
        "enabled": False,
        "revision": "UNLOCK-0001",
        "packet_sha256": value.packet_sha256,
        "approval_id": value.approval_id,
        "connector_id": value.connector_id,
        "capability": value.capability,
        "expires_at": future(),
        "production_activation_authorized": False,
        "external_send_authorized": False,
    }), encoding="utf-8")


def make_kernel(tmp_path: Path, authority: ApprovalAuthority, *, locked: bool = True) -> ConnectorKernel:
    stop = tmp_path / "stop.json"
    if not stop.exists():
        stop.write_text(json.dumps({"enabled": locked, "revision": "LOCKED-0001"}), encoding="utf-8")
    return ConnectorKernel(
        emergency_stop_path=stop,
        ledger=AppendOnlyEvidenceLedger(tmp_path / "ledger.jsonl"),
        approval_verifier=authority,
    )


def execute(kernel: ConnectorKernel, value: ExecutionPacket, authority: ApprovalAuthority):
    unlock(kernel.emergency_stop_path, value)
    return kernel.execute(value, approval(value, authority))


def test_gmail_executes_only_verified_unsent_draft_and_hashes_provider_id(tmp_path):
    authority = ApprovalAuthority()
    kernel = make_kernel(tmp_path, authority)
    adapter = GovernedGmailKernelAdapter(GmailProvider())
    kernel.register(adapter, KernelPolicy("gmail", frozenset({"CREATE_DRAFT_VERIFIED"}), 1))
    value = execute(kernel, packet("gmail", "CREATE_DRAFT_VERIFIED", {
        "to": "self@example.test", "subject": "subject", "body": "body",
        "send": False, "production_activation_authorized": False,
    }), authority)
    assert value["result"]["status"] == "DRAFT_CREATED_NOT_SENT"
    assert value["result"]["sent"] is False
    assert "provider_object_id" not in value["result"]
    assert value["result"]["provider_object_id_sha256"] == sha256(b"draft-1").hexdigest()
    assert kernel.ledger.verify()[-1]["event"] == "CONNECTOR_EXECUTION_COMPLETED"


def test_nested_credentials_and_email_are_recursively_redacted(tmp_path):
    authority = ApprovalAuthority()
    kernel = make_kernel(tmp_path, authority)
    adapter = GovernedGmailKernelAdapter(GmailProvider())
    kernel.register(adapter, KernelPolicy("gmail", adapter.capabilities, 1))
    health = kernel.health("gmail")
    assert health["identity"]["email"] == "[REDACTED]"
    assert health["identity"]["access_token"] == "[REDACTED]"


def test_locked_stop_blocks_and_unlock_must_bind_exact_packet(tmp_path):
    authority = ApprovalAuthority()
    kernel = make_kernel(tmp_path, authority)
    adapter = GovernedGitHubKernelAdapter(GitHubProvider())
    kernel.register(adapter, KernelPolicy("github", adapter.capabilities, 2))
    value = packet("github", "READ_REPOSITORY_STATE", {"mutation": False})
    record = approval(value, authority)
    with pytest.raises(PermissionError, match="locked"):
        kernel.execute(value, record)
    other = packet("github", "READ_REPOSITORY_STATE", {"mutation": False}, "other")
    unlock(kernel.emergency_stop_path, other)
    with pytest.raises(PermissionError, match="exact packet"):
        kernel.execute(value, record)


def test_independent_approval_is_required(tmp_path):
    authority = ApprovalAuthority()
    kernel = make_kernel(tmp_path, authority)
    adapter = GovernedGitHubKernelAdapter(GitHubProvider())
    kernel.register(adapter, KernelPolicy("github", adapter.capabilities, 2))
    value = packet("github", "READ_REPOSITORY_STATE", {"mutation": False})
    record = ApprovalRecord.compile(
        approval_id=value.approval_id, packet_sha256=value.packet_sha256,
        connector_id=value.connector_id, capability=value.capability,
        expires_at=value.approval_expires_at, authority_id="untrusted",
    )
    unlock(kernel.emergency_stop_path, value)
    with pytest.raises(PermissionError, match="authority"):
        kernel.execute(value, record)


def test_replay_and_rate_limit_survive_process_restart(tmp_path):
    authority = ApprovalAuthority()
    adapter = GovernedGitHubKernelAdapter(GitHubProvider())
    first_kernel = make_kernel(tmp_path, authority)
    first_kernel.register(adapter, KernelPolicy("github", adapter.capabilities, 1))
    first = packet("github", "READ_REPOSITORY_STATE", {"mutation": False}, "1")
    execute(first_kernel, first, authority)

    restarted = make_kernel(tmp_path, authority)
    restarted.register(adapter, KernelPolicy("github", adapter.capabilities, 1))
    unlock(restarted.emergency_stop_path, first)
    with pytest.raises(PermissionError, match="approval replay"):
        restarted.execute(first, approval(first, authority))
    second = packet("github", "READ_REPOSITORY_STATE", {"mutation": False}, "2")
    unlock(restarted.emergency_stop_path, second)
    with pytest.raises(PermissionError, match="rate limit"):
        restarted.execute(second, approval(second, authority))


def test_uncertain_outcome_reservation_survives_restart(tmp_path):
    class FailingProvider(GitHubProvider):
        def read_state(self, query):
            raise RuntimeError("provider uncertain")

    authority = ApprovalAuthority()
    adapter = GovernedGitHubKernelAdapter(FailingProvider())
    kernel = make_kernel(tmp_path, authority)
    kernel.register(adapter, KernelPolicy("github", adapter.capabilities, 2))
    value = packet("github", "READ_REPOSITORY_STATE", {"mutation": False})
    with pytest.raises(RuntimeError):
        execute(kernel, value, authority)
    restarted = make_kernel(tmp_path, authority)
    restarted.register(adapter, KernelPolicy("github", adapter.capabilities, 2))
    unlock(restarted.emergency_stop_path, value)
    with pytest.raises(PermissionError, match="approval replay"):
        restarted.execute(value, approval(value, authority))


def test_packet_tampering_fails_closed():
    value = packet("github", "READ_REPOSITORY_STATE", {"mutation": False})
    object.__setattr__(value, "capability", "WRITE_REPOSITORY")
    with pytest.raises(PermissionError, match="integrity"):
        value.verify()


def test_github_adapter_rejects_mutation_and_reserves_attempt(tmp_path):
    authority = ApprovalAuthority()
    kernel = make_kernel(tmp_path, authority)
    adapter = GovernedGitHubKernelAdapter(GitHubProvider())
    kernel.register(adapter, KernelPolicy("github", adapter.capabilities, 2))
    value = packet("github", "READ_REPOSITORY_STATE", {"mutation": True})
    with pytest.raises(PermissionError, match="mutation"):
        execute(kernel, value, authority)
    assert kernel.ledger.verify()[-1]["event"] == "CONNECTOR_EXECUTION_UNCERTAIN"


def test_ledger_tampering_is_detected(tmp_path):
    authority = ApprovalAuthority()
    kernel = make_kernel(tmp_path, authority)
    adapter = GovernedGitHubKernelAdapter(GitHubProvider())
    kernel.register(adapter, KernelPolicy("github", adapter.capabilities, 2))
    execute(kernel, packet("github", "READ_REPOSITORY_STATE", {"mutation": False}), authority)
    lines = kernel.ledger.path.read_text(encoding="utf-8").splitlines()
    record = json.loads(lines[0])
    record["capability"] = "TAMPERED"
    lines[0] = json.dumps(record)
    kernel.ledger.path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    with pytest.raises(ValueError, match="integrity"):
        kernel.ledger.verify()
