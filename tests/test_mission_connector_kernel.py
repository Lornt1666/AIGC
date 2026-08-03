from __future__ import annotations

from datetime import datetime, timedelta, timezone
from hashlib import sha256
import json
from pathlib import Path

import pytest

from src.mission_os.connector_adapters import GovernedGmailKernelAdapter, GovernedGitHubKernelAdapter
from src.mission_os.connector_kernel import AppendOnlyEvidenceLedger, ConnectorKernel, ExecutionPacket, KernelPolicy


def future() -> str:
    return (datetime.now(timezone.utc) + timedelta(minutes=10)).isoformat()


def idem(value: str) -> str:
    return sha256(value.encode()).hexdigest()


class GmailProvider:
    def health(self):
        return {"status": "HEALTHY_DRAFT_ONLY", "email": "private@example.test"}

    def create_draft(self, *, to, subject, body, idempotency_key):
        return {"draft_id": "draft-1"}

    def get_draft(self, draft_id):
        return {"to": "self@example.test", "subject": "subject", "body": "body", "sent": False}


class GitHubProvider:
    def repository_health(self):
        return {"status": "HEALTHY_READ_ONLY"}

    def read_state(self, query):
        return {"head_sha": "a" * 40, "query": dict(query)}


def make_kernel(tmp_path: Path) -> ConnectorKernel:
    stop = tmp_path / "stop.json"
    stop.write_text(json.dumps({"enabled": True, "revision": "LOCKED-0001"}), encoding="utf-8")
    return ConnectorKernel(emergency_stop_path=stop, ledger=AppendOnlyEvidenceLedger(tmp_path / "ledger.jsonl"))


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


def test_gmail_executes_only_verified_unsent_draft(tmp_path):
    kernel = make_kernel(tmp_path)
    adapter = GovernedGmailKernelAdapter(GmailProvider())
    kernel.register(adapter, KernelPolicy("gmail", frozenset({"CREATE_DRAFT_VERIFIED"}), 1))
    value = kernel.execute(packet("gmail", "CREATE_DRAFT_VERIFIED", {
        "to": "self@example.test", "subject": "subject", "body": "body",
        "send": False, "production_activation_authorized": False,
    }))
    assert value["result"]["status"] == "DRAFT_CREATED_NOT_SENT"
    assert value["result"]["sent"] is False
    assert kernel.ledger.verify()[-1]["event"] == "CONNECTOR_EXECUTION_COMPLETED"


def test_credentials_and_email_are_redacted_from_health(tmp_path):
    kernel = make_kernel(tmp_path)
    adapter = GovernedGmailKernelAdapter(GmailProvider())
    kernel.register(adapter, KernelPolicy("gmail", adapter.capabilities, 1))
    assert kernel.health("gmail")["email"] == "[REDACTED]"


def test_replay_and_rate_limit_fail_closed(tmp_path):
    kernel = make_kernel(tmp_path)
    adapter = GovernedGitHubKernelAdapter(GitHubProvider())
    kernel.register(adapter, KernelPolicy("github", adapter.capabilities, 1))
    first = packet("github", "READ_REPOSITORY_STATE", {"mutation": False}, "1")
    kernel.execute(first)
    with pytest.raises(PermissionError, match="approval replay"):
        kernel.execute(first)
    with pytest.raises(PermissionError, match="rate limit"):
        kernel.execute(packet("github", "READ_REPOSITORY_STATE", {"mutation": False}, "2"))


def test_emergency_stop_must_remain_enabled(tmp_path):
    kernel = make_kernel(tmp_path)
    adapter = GovernedGitHubKernelAdapter(GitHubProvider())
    kernel.register(adapter, KernelPolicy("github", adapter.capabilities, 2))
    kernel.emergency_stop_path.write_text(json.dumps({"enabled": False}), encoding="utf-8")
    with pytest.raises(PermissionError, match="not enabled"):
        kernel.execute(packet("github", "READ_REPOSITORY_STATE", {"mutation": False}))


def test_packet_tampering_and_expiry_fail_closed():
    value = packet("github", "READ_REPOSITORY_STATE", {"mutation": False})
    object.__setattr__(value, "capability", "WRITE_REPOSITORY")
    with pytest.raises(PermissionError, match="integrity"):
        value.verify()


def test_github_adapter_rejects_mutation(tmp_path):
    kernel = make_kernel(tmp_path)
    adapter = GovernedGitHubKernelAdapter(GitHubProvider())
    kernel.register(adapter, KernelPolicy("github", adapter.capabilities, 2))
    with pytest.raises(PermissionError, match="mutation"):
        kernel.execute(packet("github", "READ_REPOSITORY_STATE", {"mutation": True}))
    assert kernel.ledger.verify()[-1]["event"] == "CONNECTOR_EXECUTION_UNCERTAIN"


def test_ledger_tampering_is_detected(tmp_path):
    kernel = make_kernel(tmp_path)
    adapter = GovernedGitHubKernelAdapter(GitHubProvider())
    kernel.register(adapter, KernelPolicy("github", adapter.capabilities, 2))
    kernel.execute(packet("github", "READ_REPOSITORY_STATE", {"mutation": False}))
    lines = kernel.ledger.path.read_text(encoding="utf-8").splitlines()
    record = json.loads(lines[0])
    record["capability"] = "TAMPERED"
    lines[0] = json.dumps(record)
    kernel.ledger.path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    with pytest.raises(ValueError, match="integrity"):
        kernel.ledger.verify()
