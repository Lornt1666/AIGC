from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone
from hashlib import sha256
import json
from pathlib import Path

import pytest

from src.mission_os.connector_adapters import GovernedGmailKernelAdapter, GovernedGitHubKernelAdapter
from src.mission_os.connector_kernel import (
    AppendOnlyEvidenceLedger, ApprovalRecord, ConnectorKernel,
    ExecutionPacket, HMACApprovalVerifier, KernelPolicy,
)


def future() -> str:
    return (datetime.now(timezone.utc) + timedelta(minutes=10)).isoformat()


def idem(value: str) -> str:
    return sha256(value.encode()).hexdigest()


class ApprovalAuthority:
    deployment_ready = True

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


def make_kernel(tmp_path: Path, authority, *, locked: bool = True) -> ConnectorKernel:
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


def assert_relocked(kernel: ConnectorKernel) -> None:
    state = json.loads(kernel.emergency_stop_path.read_text(encoding="utf-8"))
    assert state["enabled"] is True
    assert state["revision"].startswith("RELOCK-")
    assert kernel.ledger.verify()[-1]["event"] == "CONNECTOR_EMERGENCY_STOP_RELOCKED"


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
    assert_relocked(kernel)


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


def test_non_deployable_approval_verifier_is_rejected(tmp_path):
    class UnsafeVerifier:
        deployment_ready = False
        def verify(self, approval, packet):
            return True

    stop = tmp_path / "stop.json"
    stop.write_text(json.dumps({"enabled": True}), encoding="utf-8")
    with pytest.raises(PermissionError, match="not deployment ready"):
        ConnectorKernel(
            emergency_stop_path=stop,
            ledger=AppendOnlyEvidenceLedger(tmp_path / "ledger.jsonl"),
            approval_verifier=UnsafeVerifier(),
        )


def test_hmac_approval_verifier_authenticates_trusted_authority():
    verifier = HMACApprovalVerifier(secret="s" * 40, trusted_authority_ids=frozenset({"human-authority-1"}))
    value = packet("github", "READ_REPOSITORY_STATE", {"mutation": False})
    unsigned = ApprovalRecord.compile(
        approval_id=value.approval_id, packet_sha256=value.packet_sha256,
        connector_id=value.connector_id, capability=value.capability,
        expires_at=value.approval_expires_at, authority_id="human-authority-1",
    )
    signature = verifier.sign(unsigned.approval_sha256, unsigned.authority_id)
    signed = ApprovalRecord.compile(
        approval_id=value.approval_id, packet_sha256=value.packet_sha256,
        connector_id=value.connector_id, capability=value.capability,
        expires_at=value.approval_expires_at, authority_id="human-authority-1",
        authority_signature=signature,
    )
    assert verifier.verify(signed, value) is True
    forged = ApprovalRecord.compile(
        approval_id=value.approval_id, packet_sha256=value.packet_sha256,
        connector_id=value.connector_id, capability=value.capability,
        expires_at=value.approval_expires_at, authority_id="human-authority-1",
        authority_signature="0" * 64,
    )
    assert verifier.verify(forged, value) is False


def test_replay_rejection_relocks_terminally(tmp_path):
    authority = ApprovalAuthority()
    adapter = GovernedGitHubKernelAdapter(GitHubProvider())
    kernel = make_kernel(tmp_path, authority)
    kernel.register(adapter, KernelPolicy("github", adapter.capabilities, 2))
    value = packet("github", "READ_REPOSITORY_STATE", {"mutation": False})
    execute(kernel, value, authority)
    unlock(kernel.emergency_stop_path, value)
    with pytest.raises(PermissionError, match="approval replay"):
        kernel.execute(value, approval(value, authority))
    assert_relocked(kernel)


def test_provider_failure_relocks_and_reservation_survives_restart(tmp_path):
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
    assert_relocked(kernel)
    restarted = make_kernel(tmp_path, authority)
    restarted.register(adapter, KernelPolicy("github", adapter.capabilities, 2))
    unlock(restarted.emergency_stop_path, value)
    with pytest.raises(PermissionError, match="approval replay"):
        restarted.execute(value, approval(value, authority))
    assert_relocked(restarted)


def test_atomic_check_and_reserve_allows_only_one_concurrent_execution(tmp_path):
    authority = ApprovalAuthority()
    adapter = GovernedGitHubKernelAdapter(GitHubProvider())
    value = packet("github", "READ_REPOSITORY_STATE", {"mutation": False})
    record = approval(value, authority)
    first = make_kernel(tmp_path, authority)
    second = make_kernel(tmp_path, authority)
    for kernel in (first, second):
        kernel.register(adapter, KernelPolicy("github", adapter.capabilities, 5))
    unlock(first.emergency_stop_path, value)

    def run(kernel):
        try:
            kernel.execute(value, record)
            return "success"
        except PermissionError:
            return "blocked"

    with ThreadPoolExecutor(max_workers=2) as pool:
        outcomes = list(pool.map(run, (first, second)))
    assert outcomes.count("success") == 1
    assert outcomes.count("blocked") == 1
    reservations = [r for r in first.ledger.verify() if r.get("event") == "CONNECTOR_EXECUTION_RESERVED"]
    assert len(reservations) == 1


def test_packet_tampering_fails_closed():
    value = packet("github", "READ_REPOSITORY_STATE", {"mutation": False})
    object.__setattr__(value, "capability", "WRITE_REPOSITORY")
    with pytest.raises(PermissionError, match="integrity"):
        value.verify()


def test_github_adapter_rejects_mutation_and_relocks(tmp_path):
    authority = ApprovalAuthority()
    kernel = make_kernel(tmp_path, authority)
    adapter = GovernedGitHubKernelAdapter(GitHubProvider())
    kernel.register(adapter, KernelPolicy("github", adapter.capabilities, 2))
    value = packet("github", "READ_REPOSITORY_STATE", {"mutation": True})
    with pytest.raises(PermissionError, match="mutation"):
        execute(kernel, value, authority)
    assert_relocked(kernel)


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
