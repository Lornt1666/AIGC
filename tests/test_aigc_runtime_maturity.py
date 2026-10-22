import unittest
from dataclasses import replace
from datetime import datetime, timedelta, timezone

import jwt
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from cryptography.hazmat.primitives import serialization

from aigc_runtime import (
    EdDsaPermitVerifier, GovernedToolAdapter, PermitBroker, RuntimeTelemetry,
    SQLiteGovernanceStore, TaskContract, ToolPermit, TrustedIssuerKey,
)
from aigc_runtime.governed_runtime import GovernanceError


def make_contract():
    return TaskContract(
        task_id="task-runtime-1", project_id="AIGC", agent_id="RX-123",
        agent_version="1.0.0", policy_version="policy-1", objective="read a test record",
        scope=("record:1",), exclusions=("write", "delete"), acceptance_criteria=("result returned",),
        risk_tier="R0", input_refs=("sha256:input",), allowed_tools=("records.read",),
        permitted_side_effects=(),
    )


class RuntimeMaturityTests(unittest.TestCase):
    def test_ed25519_verifier_accepts_trusted_issuer_and_rejects_revocation(self):
        private_key = Ed25519PrivateKey.generate()
        public_pem = private_key.public_key().public_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PublicFormat.SubjectPublicKeyInfo,
        ).decode("ascii")
        now = datetime.now(timezone.utc).replace(microsecond=0)
        issued = int(now.timestamp())
        expires = int((now + timedelta(minutes=5)).timestamp())
        permit = ToolPermit(
            permit_id="permit-crypto-1", task_id="task-runtime-1", agent_id="RX-123",
            tool_name="records.read", action="read", resource="record:1", policy_version="policy-1",
            issued_at=now.isoformat().replace("+00:00", "Z"),
            expires_at=(now + timedelta(minutes=5)).isoformat().replace("+00:00", "Z"),
            max_uses=1, issuer_id="issuer-a", key_id="key-a",
        )
        claims = {
            "iss": "issuer-a", "jti": permit.permit_id, "sub": permit.agent_id,
            "iat": issued, "exp": expires, "aud": permit.tool_name,
            "task_id": permit.task_id, "tool": permit.tool_name, "action": permit.action,
            "resource": permit.resource, "policy_version": permit.policy_version,
            "key_id": permit.key_id, "max_uses": permit.max_uses,
            "human_approval_ref": permit.human_approval_ref,
        }
        token = jwt.encode(claims, private_key, algorithm="EdDSA")
        signed = replace(permit, signature=token)
        key = TrustedIssuerKey("issuer-a", "key-a", public_pem, "ACTIVE", issued - 10, expires + 10)
        self.assertTrue(EdDsaPermitVerifier({"issuer-a"}, [key])(signed))
        self.assertFalse(EdDsaPermitVerifier({"other-issuer"}, [key])(signed))
        self.assertFalse(EdDsaPermitVerifier({"issuer-a"}, [key], revoked_permit_ids={permit.permit_id})(signed))
        self.assertFalse(EdDsaPermitVerifier({"issuer-a"}, [key], revoked_keys={("issuer-a", "key-a")})(signed))

    def test_sqlite_store_persists_and_atomically_limits_permit_uses(self):
        import tempfile
        from pathlib import Path
        with tempfile.TemporaryDirectory() as directory:
            path = str(Path(directory) / "runtime.sqlite")
            store = SQLiteGovernanceStore(path)
            store.consume_permit("permit-1", "fingerprint-1", 1)
            with self.assertRaisesRegex(GovernanceError, "permit_use_limit_exceeded"):
                store.consume_permit("permit-1", "fingerprint-1", 1)
            event_id = store.append("test_event", {"value": 7}, "2026-10-22T00:00:00Z")
            store.close()
            reopened = SQLiteGovernanceStore(path)
            self.assertEqual(len(reopened.snapshot()), 1)
            self.assertEqual(reopened.snapshot()[0]["event_id"], event_id)
            with self.assertRaisesRegex(GovernanceError, "permit_use_limit_exceeded"):
                reopened.consume_permit("permit-1", "fingerprint-1", 1)
            reopened.close()

    def test_tool_adapter_enforces_once_and_returns_idempotent_result(self):
        import tempfile
        from pathlib import Path
        with tempfile.TemporaryDirectory() as directory:
            store = SQLiteGovernanceStore(str(Path(directory) / "adapter.sqlite"))
            telemetry = RuntimeTelemetry(store)
            broker = PermitBroker(store, enabled_agent_ids={"RX-123"}, permit_verifier=lambda p: p.signature == "test-only")
            adapter = GovernedToolAdapter(broker, store, telemetry)
            now = datetime.now(timezone.utc).replace(microsecond=0)
            permit = ToolPermit(
                permit_id="permit-adapter-1", task_id="task-runtime-1", agent_id="RX-123",
                tool_name="records.read", action="read", resource="record:1", policy_version="policy-1",
                issued_at=(now - timedelta(minutes=1)).isoformat().replace("+00:00", "Z"),
                expires_at=(now + timedelta(minutes=5)).isoformat().replace("+00:00", "Z"),
                signature="test-only",
            )
            calls = []
            handler = lambda: calls.append("called") or {"record_id": "record:1"}
            first = adapter.invoke(contract=make_contract(), permit=permit, tool_name="records.read",
                action="read", resource="record:1", policy_version="policy-1",
                idempotency_key="idem-1", handler=handler)
            second = adapter.invoke(contract=make_contract(), permit=permit, tool_name="records.read",
                action="read", resource="record:1", policy_version="policy-1",
                idempotency_key="idem-1", handler=handler)
            self.assertEqual(first["status"], "SUCCEEDED")
            self.assertTrue(second["replayed"])
            self.assertEqual(len(calls), 1)
            self.assertEqual(telemetry.metrics()["invocation_count"], 1)
            store.close()

    def test_durable_invocation_key_rejects_changed_request(self):
        store = SQLiteGovernanceStore(":memory:")
        store.begin_invocation("same-key", "digest-a")
        with self.assertRaisesRegex(GovernanceError, "idempotency_key_reused_with_different_request"):
            store.begin_invocation("same-key", "digest-b")
        store.close()


if __name__ == "__main__":
    unittest.main()
