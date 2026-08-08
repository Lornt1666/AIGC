from __future__ import annotations

from dataclasses import replace
from datetime import datetime, timezone
import unittest

from src.colosseum.compute_exchange import ComputeRequirement
from src.colosseum.domain import (
    AgentCell,
    CapabilityEvidence,
    CapabilityVerdict,
    ConfidentialityClass,
    Deliverable,
    EmployerVault,
    Engagement,
    Swarm,
    Verification,
    VerificationStatus,
    WorkOrder,
)
from src.omni_forge.authorization import AuthorizationPacket, AuthorityDecision
from src.omni_forge.budget import BudgetEnvelope
from src.omni_forge.colosseum_compat import (
    CanonicalExecutionBinding,
    REPOSITORY_ONLY_ACTION,
    canonical_metadata,
)
from src.omni_forge.domain import (
    AgentInvocation,
    DataClassification,
    Environment,
)

NOW = datetime(2026, 8, 6, 20, tzinfo=timezone.utc)
EXPIRY = datetime(2099, 1, 1, tzinfo=timezone.utc)
SHA = "a" * 40
TREE = "b" * 40
DIGEST = "c" * 64
POLICY = "d" * 64
IDEMPOTENCY = "e" * 64


class CanonicalCompatibilityTests(unittest.TestCase):
    def binding(self) -> CanonicalExecutionBinding:
        vault = EmployerVault(
            vault_id="vault-1",
            employer_id="employer-1",
            confidentiality_class=ConfidentialityClass.CONFIDENTIAL,
            allowed_jurisdictions=("CA-QC",),
            retention_policy_id="retention-1",
            deletion_policy_id="deletion-1",
        )
        engagement = Engagement(
            engagement_id="engagement-1",
            employer_id="employer-1",
            vault_id=vault.vault_id,
            statement_of_work_id="sow-1",
            acceptance_criteria=("criterion-1",),
            deadline=EXPIRY,
            authorized=True,
        )
        work_order = WorkOrder(
            work_order_id="work-order-1",
            engagement_id=engagement.engagement_id,
            objective="Produce a verified repository deliverable",
            requirement_ids=("compute-1",),
            acceptance_criteria=("criterion-1",),
            authorized=True,
        )
        cell = AgentCell(
            agent_cell_id="cell-1",
            role="verification_agent",
            allowed_tools=("github.read",),
            allowed_data_scopes=(vault.vault_id,),
            output_schema_id="schema-1",
            maximum_cost_cad=10.0,
            maximum_tokens=2_000,
        )
        swarm = Swarm(
            swarm_id="swarm-1",
            engagement_id=engagement.engagement_id,
            work_order_id=work_order.work_order_id,
            objective=work_order.objective,
            agent_cells=(cell,),
            compute_budget_cad=10.0,
            token_budget=2_000,
            confidentiality_class=ConfidentialityClass.CONFIDENTIAL,
            jurisdiction_policy_id="ca-qc-only",
            verification_policy_id="independent",
            emergency_stop_epoch=0,
        )
        deliverable = Deliverable(
            deliverable_id="deliverable-1",
            work_order_id=work_order.work_order_id,
            artifact_ids=("artifact-1",),
            acceptance_criteria=work_order.acceptance_criteria,
        )
        verification = Verification(
            verification_id="verification-1",
            deliverable_id=deliverable.deliverable_id,
            verifier_identity="verifier-1",
            status=VerificationStatus.PASS,
            checks=("criterion-1",),
            evidence_refs=("receipt-1",),
        )
        capability = CapabilityEvidence(
            capability_evidence_id="capability-1",
            discipline="Software Engineering",
            skill="Repository verification",
            verdict=CapabilityVerdict.VERIFIED_CAPABLE,
            benchmark_ids=("benchmark-1",),
            accepted_deliverable_ids=(),
            validated_attempts=1,
            successful_attempts=1,
            human_review_required=False,
            evidence_refs=("capability-receipt-1",),
            last_verified_at=NOW,
        )
        compute = ComputeRequirement(
            requirement_id="compute-1",
            workload_class="repository-verification",
            minimum_quality=0.9,
            minimum_reliability=0.9,
            minimum_availability=0.9,
            minimum_security_level=2,
            minimum_privacy_level=2,
            maximum_latency_ms=60_000,
            maximum_cost_cad=10.0,
            confidentiality_class=ConfidentialityClass.CONFIDENTIAL,
            allowed_jurisdictions=("CA-QC",),
            required_capabilities=("repository-read",),
        )
        metadata = canonical_metadata(
            employer_id=vault.employer_id,
            employer_vault_id=vault.vault_id,
            engagement_id=engagement.engagement_id,
            work_order_id=work_order.work_order_id,
            task_id="task-1",
            agent_cell_id=cell.agent_cell_id,
            swarm_id=swarm.swarm_id,
            deliverable_id=deliverable.deliverable_id,
            verification_id=verification.verification_id,
            capability_evidence_id=capability.capability_evidence_id,
            compute_requirement_id=compute.requirement_id,
            output_schema_id=cell.output_schema_id,
            repository_sha=SHA,
            repository_tree_sha=TREE,
            idempotency_key_digest=IDEMPOTENCY,
        )
        invocation = AgentInvocation.compile(
            invocation_id="invocation-1",
            agent_role=cell.role,
            allowed_inputs=("repository-diff",),
            allowed_outputs=("verification-receipt",),
            allowed_tools=("github.read",),
            maximum_tokens=1_000,
            maximum_cost_cad=5.0,
            deadline_epoch_seconds=1,
            data_classification=DataClassification.CONFIDENTIAL,
            authorization_scope=(
                "employer:employer-1",
                "vault:vault-1",
                "engagement:engagement-1",
                "work_order:work-order-1",
                "task:task-1",
            ),
            parent_trace_id="trace-1",
            schema_digest=DIGEST,
            environment=Environment.TEST,
            metadata=metadata,
        )
        authorization = AuthorizationPacket(
            packet_id="packet-1",
            actor_id="human-reviewer",
            environment="TEST",
            action=REPOSITORY_ONLY_ACTION,
            target=work_order.work_order_id,
            repository_sha=SHA,
            repository_tree_sha=TREE,
            schema_digest=DIGEST,
            policy_digest=POLICY,
            idempotency_key_digest=IDEMPOTENCY,
            expires_at=EXPIRY.isoformat(),
            decision=AuthorityDecision.ALLOW_REPOSITORY_ONLY,
        )
        return CanonicalExecutionBinding(
            employer_id=vault.employer_id,
            task_id="task-1",
            employer_vault=vault,
            engagement=engagement,
            work_order=work_order,
            agent_cell=cell,
            swarm=swarm,
            deliverable=deliverable,
            verification=verification,
            capability_evidence=capability,
            compute_requirement=compute,
            invocation=invocation,
            budget=BudgetEnvelope(
                maximum_tokens=1_000,
                maximum_cost_cad=5.0,
            ),
            authorization=authorization,
        )

    def test_valid_binding_verifies(self) -> None:
        self.binding().verify(now=NOW)

    def test_cross_employer_binding_is_rejected(self) -> None:
        binding = self.binding()
        with self.assertRaises(ValueError):
            replace(binding, employer_id="employer-2").verify(now=NOW)

    def test_tampered_task_metadata_is_rejected(self) -> None:
        binding = self.binding()
        metadata = dict(binding.invocation.metadata)
        metadata["task_id"] = "task-other"
        invocation = replace(binding.invocation, metadata=metadata)
        with self.assertRaises(PermissionError):
            replace(binding, invocation=invocation).verify(now=NOW)

    def test_agent_tools_cannot_exceed_agent_cell(self) -> None:
        binding = self.binding()
        invocation = AgentInvocation.compile(
            invocation_id=binding.invocation.invocation_id,
            agent_role=binding.invocation.agent_role,
            allowed_inputs=binding.invocation.allowed_inputs,
            allowed_outputs=binding.invocation.allowed_outputs,
            allowed_tools=("github.read", "github.write"),
            maximum_tokens=binding.invocation.maximum_tokens,
            maximum_cost_cad=binding.invocation.maximum_cost_cad,
            deadline_epoch_seconds=binding.invocation.deadline_epoch_seconds,
            data_classification=binding.invocation.data_classification,
            authorization_scope=binding.invocation.authorization_scope,
            parent_trace_id=binding.invocation.parent_trace_id,
            schema_digest=binding.invocation.schema_digest,
            environment=binding.invocation.environment,
            metadata=binding.invocation.metadata,
        )
        with self.assertRaises(PermissionError):
            replace(binding, invocation=invocation).verify(now=NOW)

    def test_compute_jurisdiction_cannot_exceed_vault(self) -> None:
        binding = self.binding()
        compute = replace(
            binding.compute_requirement,
            allowed_jurisdictions=("CA-QC", "US"),
        )
        with self.assertRaises(PermissionError):
            replace(binding, compute_requirement=compute).verify(now=NOW)

    def test_not_qualified_capability_is_rejected(self) -> None:
        binding = self.binding()
        capability = replace(
            binding.capability_evidence,
            verdict=CapabilityVerdict.NOT_QUALIFIED,
        )
        with self.assertRaises(PermissionError):
            replace(binding, capability_evidence=capability).verify(now=NOW)

    def test_app_store_tool_is_rejected(self) -> None:
        with self.assertRaises(PermissionError):
            AgentInvocation.compile(
                invocation_id="invocation-app-store",
                agent_role="release_agent",
                allowed_inputs=("archive",),
                allowed_outputs=("receipt",),
                allowed_tools=("app_store.submit",),
                maximum_tokens=100,
                maximum_cost_cad=0,
                deadline_epoch_seconds=1,
                data_classification=DataClassification.PUBLIC,
                authorization_scope=("none",),
                parent_trace_id="trace-app-store",
                schema_digest=DIGEST,
            )

    def test_authority_packet_rejects_merge_or_app_store(self) -> None:
        binding = self.binding()
        for field in ("merge", "app_store_submission"):
            packet = replace(binding.authorization, **{field: True})
            with self.assertRaises(PermissionError):
                packet.verify(now=NOW)


if __name__ == "__main__":
    unittest.main()
