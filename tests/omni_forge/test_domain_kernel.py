from __future__ import annotations

from datetime import datetime, timedelta, timezone
import unittest

from src.omni_forge.authorization import AuthorizationPacket, AuthorityDecision
from src.omni_forge.budget import BudgetEnvelope
from src.omni_forge.domain import AgentInvocation, DataClassification, Environment
from src.omni_forge.evidence import EvidenceReceipt
from src.omni_forge.graph_validator import GraphValidationError, validate_graph
from src.omni_forge.state_machine import ExecutionState, transition

SHA = "a" * 40
TREE = "b" * 40
DIGEST = "c" * 64


class DomainKernelTests(unittest.TestCase):
    def test_safe_agent_invocation_compiles(self) -> None:
        invocation = AgentInvocation.compile(
            invocation_id="invocation-001",
            agent_role="verification_agent",
            allowed_inputs=["repository_diff"],
            allowed_outputs=["verification_receipt"],
            allowed_tools=["github.read"],
            maximum_tokens=1000,
            maximum_cost_cad=1.5,
            deadline_epoch_seconds=1,
            data_classification=DataClassification.SANITIZED_NON_PERSONAL,
            authorization_scope=["repository.read"],
            parent_trace_id="trace-001",
            schema_digest=DIGEST,
        )
        self.assertEqual(invocation.environment, Environment.TEST)

    def test_prohibited_tool_is_rejected(self) -> None:
        with self.assertRaises(PermissionError):
            AgentInvocation.compile(
                invocation_id="invocation-002",
                agent_role="execution_agent",
                allowed_inputs=["plan"],
                allowed_outputs=["result"],
                allowed_tools=["cloud.deploy"],
                maximum_tokens=1000,
                maximum_cost_cad=1,
                deadline_epoch_seconds=1,
                data_classification=DataClassification.PUBLIC,
                authorization_scope=["none"],
                parent_trace_id="trace-002",
                schema_digest=DIGEST,
            )

    def test_state_machine_rejects_skipped_transition(self) -> None:
        with self.assertRaises(ValueError):
            transition(ExecutionState.RECEIVED, ExecutionState.EXECUTING)

    def test_authorized_transition_requires_verification(self) -> None:
        with self.assertRaises(PermissionError):
            transition(
                ExecutionState.AUTHORIZATION_REQUIRED,
                ExecutionState.AUTHORIZED,
            )

    def test_external_execution_requires_idempotency(self) -> None:
        with self.assertRaises(PermissionError):
            transition(
                ExecutionState.AUTHORIZED,
                ExecutionState.EXECUTING,
                authorization_verified=True,
                external_effect_requested=True,
                idempotency_key_present=False,
            )

    def test_budget_blocks_fourth_repair(self) -> None:
        budget = BudgetEnvelope(1000, 10, maximum_attempts=3)
        budget = budget.reserve(tokens=100, cost_cad=1)
        budget = budget.reserve(tokens=100, cost_cad=1)
        budget = budget.reserve(tokens=100, cost_cad=1)
        with self.assertRaises(PermissionError):
            budget.reserve(tokens=100, cost_cad=1)

    def test_graph_requires_authorization_and_idempotency(self) -> None:
        graph = {
            "nodes": [
                {
                    "node_id": "deploy",
                    "node_type": "ACTION",
                    "external_effect": True,
                    "output_schema_digest": DIGEST,
                }
            ],
            "edges": [],
        }
        with self.assertRaises(GraphValidationError):
            validate_graph(graph)

    def test_graph_rejects_unbounded_cycle(self) -> None:
        graph = {
            "nodes": [
                {"node_id": "a", "node_type": "TASK", "output_schema_digest": DIGEST},
                {"node_id": "b", "node_type": "TASK", "output_schema_digest": DIGEST},
            ],
            "edges": [
                {"source": "a", "target": "b"},
                {"source": "b", "target": "a"},
            ],
        }
        with self.assertRaises(GraphValidationError):
            validate_graph(graph)

    def test_authorization_cannot_grant_consequential_authority(self) -> None:
        packet = AuthorizationPacket(
            packet_id="packet-001",
            actor_id="human-reviewer",
            environment="STAGING",
            action="repository.review",
            target="Lornt1666/AIGC",
            repository_sha=SHA,
            repository_tree_sha=TREE,
            schema_digest=DIGEST,
            policy_digest=DIGEST,
            idempotency_key_digest=DIGEST,
            expires_at=(datetime.now(timezone.utc) + timedelta(hours=1)).isoformat(),
            decision=AuthorityDecision.ALLOW_REPOSITORY_ONLY,
            production_activation=True,
        )
        with self.assertRaises(PermissionError):
            packet.verify()

    def test_evidence_detects_tampering(self) -> None:
        receipt = EvidenceReceipt.compile(
            receipt_id="receipt-001",
            event_type="SCHEMA_VALIDATED",
            repository_sha=SHA,
            repository_tree_sha=TREE,
            schema_version="1.0.0",
            payload_digest=DIGEST,
        )
        receipt.verify()
        with self.assertRaises(PermissionError):
            receipt.tampered(event_type="COMMITTED").verify()


if __name__ == "__main__":
    unittest.main()
