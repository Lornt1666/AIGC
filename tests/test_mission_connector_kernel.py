from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone
from hashlib import sha256
import json
from pathlib import Path
import socket

import pytest

from src.mission_os.connector_adapters import GovernedGmailKernelAdapter, GovernedGitHubKernelAdapter
from src.mission_os.connector_kernel import (
    AppendOnlyEvidenceLedger, ApprovalRecord, ConnectorKernel, CriticalRelockError,
    ExecutionPacket, HMACApprovalVerifier, KernelPolicy,
)
import src.mission_os.connector_kernel_v2 as kernel_module


def future(minutes: int = 10) -> str:
    return (datetime.now(timezone.utc) + timedelta(minutes=minutes)).isoformat()


def idem(value: str) -> str:
    return sha256(value.encode()).hexdigest()


class ApprovalAuthority:
    deployment_ready = True
    def __init__(self) -> None: self.allowed: set[str] = set()
    def authorize(self, approval: ApprovalRecord) -> None: self.allowed.add(approval.approval_sha256)
    def verify(self, approval: ApprovalRecord, packet: ExecutionPacket) -> bool:
        return approval.approval_sha256 in self.allowed and approval.packet_sha256 == packet.packet_sha256


class GmailProvider:
    def health(self):
        return {"status": "HEALTHY_DRAFT_ONLY", "identity": {"email": "private@example.test", "access_token": "secret"}}
    def create_draft(self, *, to, subject, body, idempotency_key): return {"draft_id": "draft-1"}
    def get_draft(self, draft_id):
        return {"to": "self@example.test", "subject": "subject", "body": "body", "sent": False}


class GitHubProvider:
    def __init__(self) -> None: self.calls = 0
    def repository_health(self): return {"status": "HEALTHY_READ_ONLY"}
    def read_state(self, query):
        self.calls += 1
        return {"head_sha": "a" * 40, "query": dict(query)}


def packet(connector: str, capability: str, payload: dict, suffix: str = "1") -> ExecutionPacket:
    return ExecutionPacket.compile(
        connector_id=connector, capability=capability, payload=payload,
        idempotency_key=idem("idempotency-" + suffix), approval_id="approval-" + suffix,
        approval_expires_at=future(), policy_revision="POLICY-0001",
    )


def approval(value: ExecutionPacket, authority: ApprovalAuthority) -> ApprovalRecord:
    record = ApprovalRecord.compile(
        approval_id=value.approval_id, packet_sha256=value.packet_sha256,
        connector_id=value.connector_id, capability=value.capability,
        expires_at=value.approval_expires_at, authority_id="human-authority-1",
    )
    authority.authorize(record)
    return record


def unlock(stop: Path, value: ExecutionPacket) -> None:
    stop.write_text(json.dumps({
        "enabled": False, "revision": "UNLOCK-0001", "packet_sha256": value.packet_sha256,
        "approval_id": value.approval_id, "connector_id": value.connector_id,
        "capability": value.capability, "expires_at": future(),
        "production_activation_authorized": False, "external_send_authorized": False,
    }), encoding="utf-8")


def make_kernel(tmp_path: Path, authority, *, stale_lock_seconds: float = 30.0) -> ConnectorKernel:
    stop = tmp_path / "stop.json"
    if not stop.exists():
        stop.write_text(json.dumps({"enabled": True, "revision": "LOCKED-0001"}), encoding="utf-8")
    return ConnectorKernel(
        emergency_stop_path=stop,
        ledger=AppendOnlyEvidenceLedger(tmp_path / "ledger.jsonl", stale_lock_seconds=stale_lock_seconds),
        approval_verifier=authority,
    )


def execute(kernel: ConnectorKernel, value: ExecutionPacket, authority: ApprovalAuthority):
    unlock(kernel.emergency_stop_path, value)
    return kernel.execute(value, approval(value, authority))


def assert_relocked(kernel: ConnectorKernel) -> None:
    state = json.loads(kernel.emergency_stop_path.read_text(encoding="utf-8"))
    assert state["enabled"] is True
    assert state["revision"].startswith("RELOCK-")
    assert "active_execution_lease" not in state
    assert kernel.ledger.verify()[-1]["event"] == "CONNECTOR_EMERGENCY_STOP_RELOCKED"


def test_gmail_verified_unsent_draft_hashes_provider_id_and_relocks(tmp_path):
    authority = ApprovalAuthority(); kernel = make_kernel(tmp_path, authority)
    adapter = GovernedGmailKernelAdapter(GmailProvider())
    kernel.register(adapter, KernelPolicy("gmail", adapter.capabilities, 1))
    result = execute(kernel, packet("gmail", "CREATE_DRAFT_VERIFIED", {
        "to": "self@example.test", "subject": "subject", "body": "body",
        "send": False, "production_activation_authorized": False,
    }), authority)
    assert result["result"]["sent"] is False
    assert result["result"]["provider_object_id_sha256"] == sha256(b"draft-1").hexdigest()
    assert_relocked(kernel)


def test_recursive_redaction(tmp_path):
    authority = ApprovalAuthority(); kernel = make_kernel(tmp_path, authority)
    adapter = GovernedGmailKernelAdapter(GmailProvider())
    kernel.register(adapter, KernelPolicy("gmail", adapter.capabilities, 1))
    health = kernel.health("gmail")
    assert health["identity"] == {"email": "[REDACTED]", "access_token": "[REDACTED]"}


def test_non_deployable_verifier_rejected(tmp_path):
    class Unsafe:
        deployment_ready = False
        def verify(self, approval, packet): return True
    with pytest.raises(PermissionError, match="not deployment ready"):
        make_kernel(tmp_path, Unsafe())


def test_hmac_verifier_requires_authentic_signature():
    verifier = HMACApprovalVerifier(secret="s" * 40, trusted_authority_ids=frozenset({"human-authority-1"}))
    value = packet("github", "READ_REPOSITORY_STATE", {"mutation": False})
    unsigned = ApprovalRecord.compile(approval_id=value.approval_id, packet_sha256=value.packet_sha256,
        connector_id=value.connector_id, capability=value.capability, expires_at=value.approval_expires_at,
        authority_id="human-authority-1")
    signed = ApprovalRecord.compile(approval_id=value.approval_id, packet_sha256=value.packet_sha256,
        connector_id=value.connector_id, capability=value.capability, expires_at=value.approval_expires_at,
        authority_id="human-authority-1", authority_signature=verifier.sign(unsigned.approval_sha256, unsigned.authority_id))
    assert verifier.verify(signed, value)
    assert not verifier.verify(ApprovalRecord.compile(approval_id=value.approval_id,
        packet_sha256=value.packet_sha256, connector_id=value.connector_id, capability=value.capability,
        expires_at=value.approval_expires_at, authority_id="human-authority-1", authority_signature="0" * 64), value)


def test_replay_rejection_consumes_unlock_to_lease_then_relocks(tmp_path):
    authority = ApprovalAuthority(); provider = GitHubProvider(); adapter = GovernedGitHubKernelAdapter(provider)
    kernel = make_kernel(tmp_path, authority); kernel.register(adapter, KernelPolicy("github", adapter.capabilities, 2))
    value = packet("github", "READ_REPOSITORY_STATE", {"mutation": False})
    execute(kernel, value, authority)
    unlock(kernel.emergency_stop_path, value)
    with pytest.raises(PermissionError, match="approval replay"):
        kernel.execute(value, approval(value, authority))
    assert provider.calls == 1
    assert_relocked(kernel)


def test_provider_failure_is_uncertain_and_relocked(tmp_path):
    class Failing(GitHubProvider):
        def read_state(self, query):
            self.calls += 1
            raise RuntimeError("provider uncertain")
    authority = ApprovalAuthority(); adapter = GovernedGitHubKernelAdapter(Failing())
    kernel = make_kernel(tmp_path, authority); kernel.register(adapter, KernelPolicy("github", adapter.capabilities, 2))
    with pytest.raises(RuntimeError):
        execute(kernel, packet("github", "READ_REPOSITORY_STATE", {"mutation": False}), authority)
    assert_relocked(kernel)
    assert any(record["event"] == "CONNECTOR_EXECUTION_UNCERTAIN" for record in kernel.ledger.verify())


def test_atomic_lease_allows_only_one_concurrent_provider_effect(tmp_path):
    authority = ApprovalAuthority(); provider = GitHubProvider(); adapter = GovernedGitHubKernelAdapter(provider)
    value = packet("github", "READ_REPOSITORY_STATE", {"mutation": False}); record = approval(value, authority)
    first = make_kernel(tmp_path, authority); second = make_kernel(tmp_path, authority)
    for kernel in (first, second): kernel.register(adapter, KernelPolicy("github", adapter.capabilities, 5))
    unlock(first.emergency_stop_path, value)
    def run(kernel):
        try: kernel.execute(value, record); return "success"
        except PermissionError: return "blocked"
    with ThreadPoolExecutor(max_workers=2) as pool:
        outcomes = list(pool.map(run, (first, second)))
    assert outcomes.count("success") == 1 and outcomes.count("blocked") == 1
    assert provider.calls == 1
    assert len([r for r in first.ledger.verify() if r.get("event") == "CONNECTOR_EXECUTION_RESERVED"]) == 1
    assert_relocked(first)


def test_pre_effect_lease_revalidation_blocks_tampered_lease(tmp_path):
    authority = ApprovalAuthority(); provider = GitHubProvider(); adapter = GovernedGitHubKernelAdapter(provider)
    kernel = make_kernel(tmp_path, authority); kernel.register(adapter, KernelPolicy("github", adapter.capabilities, 2))
    value = packet("github", "READ_REPOSITORY_STATE", {"mutation": False})
    original = kernel._verify_execution_lease
    def tamper(packet_value, lease):
        state = json.loads(kernel.emergency_stop_path.read_text(encoding="utf-8"))
        state["active_execution_lease"]["lease_id"] = "tampered"
        kernel.emergency_stop_path.write_text(json.dumps(state), encoding="utf-8")
        original(packet_value, lease)
    kernel._verify_execution_lease = tamper  # type: ignore[method-assign]
    with pytest.raises(PermissionError, match="lease binding"):
        execute(kernel, value, authority)
    assert provider.calls == 0
    assert_relocked(kernel)


def test_relock_failure_writes_durable_critical_evidence(tmp_path, monkeypatch):
    authority = ApprovalAuthority(); provider = GitHubProvider(); adapter = GovernedGitHubKernelAdapter(provider)
    kernel = make_kernel(tmp_path, authority); kernel.register(adapter, KernelPolicy("github", adapter.capabilities, 2))
    value = packet("github", "READ_REPOSITORY_STATE", {"mutation": False})
    original = kernel_module._atomic_json_write
    calls = {"count": 0}
    def fail_relock(path, data):
        if data.get("revision", "").startswith("RELOCK-"):
            calls["count"] += 1
            raise OSError("forced relock failure")
        original(path, data)
    monkeypatch.setattr(kernel_module, "_atomic_json_write", fail_relock)
    with pytest.raises(CriticalRelockError):
        execute(kernel, value, authority)
    assert calls["count"] == kernel.relock_attempts
    records = [json.loads(line) for line in kernel.critical_path.read_text(encoding="utf-8").splitlines()]
    assert records[-1]["event"] == "CONNECTOR_RELOCK_CRITICAL_FAILURE"
    assert "forced relock failure" not in json.dumps(records[-1])


def test_stale_transaction_lock_is_recovered(tmp_path):
    ledger = AppendOnlyEvidenceLedger(tmp_path / "ledger.jsonl", lock_timeout_seconds=0.5, stale_lock_seconds=0.01)
    ledger.lock_path.mkdir(parents=True)
    ledger.owner_path.write_text(json.dumps({"token": "dead", "pid": 99999999,
        "hostname": socket.gethostname(), "created_at": (datetime.now(timezone.utc) - timedelta(minutes=1)).isoformat()}), encoding="utf-8")
    with ledger.transaction():
        assert ledger.owner_path.exists()
    assert not ledger.lock_path.exists()


def test_live_transaction_lock_is_not_stolen(tmp_path):
    ledger = AppendOnlyEvidenceLedger(tmp_path / "ledger.jsonl", lock_timeout_seconds=0.05, stale_lock_seconds=0.01)
    with ledger.transaction():
        with pytest.raises(TimeoutError):
            with ledger.transaction():
                pass


def test_github_mutation_is_prohibited_and_relocked(tmp_path):
    authority = ApprovalAuthority(); adapter = GovernedGitHubKernelAdapter(GitHubProvider())
    kernel = make_kernel(tmp_path, authority); kernel.register(adapter, KernelPolicy("github", adapter.capabilities, 2))
    with pytest.raises(PermissionError, match="mutation"):
        execute(kernel, packet("github", "READ_REPOSITORY_STATE", {"mutation": True}), authority)
    assert_relocked(kernel)


def test_ledger_tampering_detected(tmp_path):
    authority = ApprovalAuthority(); adapter = GovernedGitHubKernelAdapter(GitHubProvider())
    kernel = make_kernel(tmp_path, authority); kernel.register(adapter, KernelPolicy("github", adapter.capabilities, 2))
    execute(kernel, packet("github", "READ_REPOSITORY_STATE", {"mutation": False}), authority)
    lines = kernel.ledger.path.read_text(encoding="utf-8").splitlines()
    record = json.loads(lines[0]); record["capability"] = "TAMPERED"; lines[0] = json.dumps(record)
    kernel.ledger.path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    with pytest.raises(ValueError, match="integrity"):
        kernel.ledger.verify()
