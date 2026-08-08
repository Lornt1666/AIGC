from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
import re
from typing import Mapping

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
    WorkOrder,
)

from .authorization import AuthorizationPacket, AuthorityDecision
from .budget import BudgetEnvelope
from .domain import AgentInvocation, DataClassification

CANONICAL_BINDING_SCHEMA_VERSION = "1.0.0"
REPOSITORY_ONLY_ACTION = "omni_forge.execute_work_order"

_GIT_SHA = re.compile(r"^[a-f0-9]{40}$")
_SHA256 = re.compile(r"^[a-f0-9]{64}$")

_VAULT_CLASSIFICATION_RANK = {
    ConfidentialityClass.PUBLIC: 0,
    ConfidentialityClass.INTERNAL: 1,
    ConfidentialityClass.CONFIDENTIAL: 2,
    ConfidentialityClass.RESTRICTED: 4,
}

_INVOCATION_CLASSIFICATION_RANK = {
    DataClassification.PUBLIC: 0,
    DataClassification.SANITIZED_NON_PERSONAL: 1,
    DataClassification.CONFIDENTIAL: 2,
    DataClassification.PERSONAL: 3,
    DataClassification.RESTRICTED: 4,
}

_EXECUTABLE_CAPABILITY_VERDICTS = frozenset(
    {
        CapabilityVerdict.VERIFIED_CAPABLE,
        CapabilityVerdict.CAPABLE_WITH_REVIEW,
        CapabilityVerdict.CAPABLE_WITH_SPECIALIST,
    }
)


def _require_text(name: str, value: str) -> str:
    value = value.strip()
    if not value:
        raise ValueError(f"{name} must be non-empty")
    return value


def _require_git_sha(name: str, value: str) -> str:
    if not _GIT_SHA.fullmatch(value):
        raise ValueError(f"{name} must be a lowercase 40-character Git SHA")
    return value


def _require_sha256(name: str, value: str) -> str:
    if not _SHA256.fullmatch(value):
        raise ValueError(f"{name} must be a lowercase SHA-256 digest")
    return value


def canonical_metadata(
    *,
    employer_id: str,
    employer_vault_id: str,
    engagement_id: str,
    work_order_id: str,
    task_id: str,
    agent_cell_id: str,
    swarm_id: str,
    deliverable_id: str,
    verification_id: str,
    capability_evidence_id: str,
    compute_requirement_id: str,
    output_schema_id: str,
    repository_sha: str,
    repository_tree_sha: str,
    idempotency_key_digest: str,
) -> dict[str, str]:
    """Build deterministic metadata without introducing a second product ontology.

    Current canonical main has typed EmployerVault, Engagement, WorkOrder,
    AgentCell, Swarm, Deliverable, Verification, CapabilityEvidence and
    ComputeRequirement contracts. Employer and Task remain identifier anchors
    here until canonical typed contracts are introduced in ``src.colosseum``.
    """

    values = {
        "binding_schema_version": CANONICAL_BINDING_SCHEMA_VERSION,
        "employer_id": employer_id,
        "employer_vault_id": employer_vault_id,
        "engagement_id": engagement_id,
        "work_order_id": work_order_id,
        "task_id": task_id,
        "agent_cell_id": agent_cell_id,
        "swarm_id": swarm_id,
        "deliverable_id": deliverable_id,
        "verification_id": verification_id,
        "capability_evidence_id": capability_evidence_id,
        "compute_requirement_id": compute_requirement_id,
        "output_schema_id": output_schema_id,
        "repository_sha": repository_sha,
        "repository_tree_sha": repository_tree_sha,
        "idempotency_key_digest": idempotency_key_digest,
    }
    for name in (
        "employer_id",
        "employer_vault_id",
        "engagement_id",
        "work_order_id",
        "task_id",
        "agent_cell_id",
        "swarm_id",
        "deliverable_id",
        "verification_id",
        "capability_evidence_id",
        "compute_requirement_id",
        "output_schema_id",
    ):
        values[name] = _require_text(name, values[name])
    values["repository_sha"] = _require_git_sha(
        "repository_sha", values["repository_sha"]
    )
    values["repository_tree_sha"] = _require_git_sha(
        "repository_tree_sha", values["repository_tree_sha"]
    )
    values["idempotency_key_digest"] = _require_sha256(
        "idempotency_key_digest", values["idempotency_key_digest"]
    )
    return values


@dataclass(frozen=True)
class CanonicalExecutionBinding:
    """Fail-closed adapter from OMNI-FORGE execution to canonical AIGC contracts."""

    employer_id: str
    task_id: str
    employer_vault: EmployerVault
    engagement: Engagement
    work_order: WorkOrder
    agent_cell: AgentCell
    swarm: Swarm
    deliverable: Deliverable
    verification: Verification
    capability_evidence: CapabilityEvidence
    compute_requirement: ComputeRequirement
    invocation: AgentInvocation
    budget: BudgetEnvelope
    authorization: AuthorizationPacket

    @property
    def metadata(self) -> Mapping[str, str]:
        return canonical_metadata(
            employer_id=self.employer_id,
            employer_vault_id=self.employer_vault.vault_id,
            engagement_id=self.engagement.engagement_id,
            work_order_id=self.work_order.work_order_id,
            task_id=self.task_id,
            agent_cell_id=self.agent_cell.agent_cell_id,
            swarm_id=self.swarm.swarm_id,
            deliverable_id=self.deliverable.deliverable_id,
            verification_id=self.verification.verification_id,
            capability_evidence_id=self.capability_evidence.capability_evidence_id,
            compute_requirement_id=self.compute_requirement.requirement_id,
            output_schema_id=self.agent_cell.output_schema_id,
            repository_sha=self.authorization.repository_sha,
            repository_tree_sha=self.authorization.repository_tree_sha,
            idempotency_key_digest=self.authorization.idempotency_key_digest,
        )

    def verify(self, *, now: datetime | None = None) -> None:
        employer_id = _require_text("employer_id", self.employer_id)
        task_id = _require_text("task_id", self.task_id)
        self.invocation.verify()
        self.budget.verify()
        self.authorization.verify(now=now)

        if self.authorization.decision is not AuthorityDecision.ALLOW_REPOSITORY_ONLY:
            raise PermissionError(
                "canonical binding permits repository-only authority in this slice"
            )
        if self.employer_vault.employer_id != employer_id:
            raise ValueError("EmployerVault belongs to a different Employer")
        if self.engagement.employer_id != employer_id:
            raise ValueError("Engagement belongs to a different Employer")
        if self.engagement.vault_id != self.employer_vault.vault_id:
            raise ValueError("Engagement is not bound to the EmployerVault")
        if self.work_order.engagement_id != self.engagement.engagement_id:
            raise ValueError("WorkOrder belongs to a different Engagement")
        if not self.engagement.authorized or not self.work_order.authorized:
            raise PermissionError(
                "Engagement and WorkOrder must both be human-authorized"
            )
        if self.swarm.engagement_id != self.engagement.engagement_id:
            raise ValueError("Swarm belongs to a different Engagement")
        if self.swarm.work_order_id != self.work_order.work_order_id:
            raise ValueError("Swarm belongs to a different WorkOrder")

        matching_cells = tuple(
            cell
            for cell in self.swarm.agent_cells
            if cell.agent_cell_id == self.agent_cell.agent_cell_id
        )
        if len(matching_cells) != 1 or matching_cells[0] != self.agent_cell:
            raise ValueError("AgentCell is not uniquely bound into the Swarm")
        if self.deliverable.work_order_id != self.work_order.work_order_id:
            raise ValueError("Deliverable belongs to a different WorkOrder")
        if self.verification.deliverable_id != self.deliverable.deliverable_id:
            raise ValueError("Verification belongs to a different Deliverable")
        if (
            self.compute_requirement.requirement_id
            not in self.work_order.requirement_ids
        ):
            raise ValueError(
                "ComputeRequirement is not declared by the WorkOrder"
            )
        if (
            self.capability_evidence.verdict
            not in _EXECUTABLE_CAPABILITY_VERDICTS
        ):
            raise PermissionError(
                "CapabilityEvidence does not admit bounded execution"
            )
        if not self.capability_evidence.evidence_refs:
            raise ValueError("CapabilityEvidence requires retained evidence")

        if self.invocation.agent_role != self.agent_cell.role:
            raise ValueError("AgentInvocation role does not match AgentCell role")
        if not set(self.invocation.allowed_tools).issubset(
            self.agent_cell.allowed_tools
        ):
            raise PermissionError(
                "AgentInvocation tools exceed AgentCell permissions"
            )
        if self.employer_vault.vault_id not in self.agent_cell.allowed_data_scopes:
            raise PermissionError(
                "AgentCell lacks the bound EmployerVault data scope"
            )
        if self.invocation.maximum_tokens > self.agent_cell.maximum_tokens:
            raise PermissionError(
                "AgentInvocation token ceiling exceeds AgentCell ceiling"
            )
        if self.invocation.maximum_cost_cad > self.agent_cell.maximum_cost_cad:
            raise PermissionError(
                "AgentInvocation cost ceiling exceeds AgentCell ceiling"
            )

        maximum_tokens = min(
            self.invocation.maximum_tokens,
            self.agent_cell.maximum_tokens,
            self.swarm.token_budget,
        )
        if self.budget.maximum_tokens > maximum_tokens:
            raise PermissionError(
                "BudgetEnvelope token ceiling exceeds canonical execution ceilings"
            )
        maximum_cost_cad = min(
            self.invocation.maximum_cost_cad,
            self.agent_cell.maximum_cost_cad,
            self.swarm.compute_budget_cad,
            self.compute_requirement.maximum_cost_cad,
        )
        if self.budget.maximum_cost_cad > maximum_cost_cad:
            raise PermissionError(
                "BudgetEnvelope cost ceiling exceeds canonical execution ceilings"
            )

        vault_rank = _VAULT_CLASSIFICATION_RANK[
            self.employer_vault.confidentiality_class
        ]
        if _VAULT_CLASSIFICATION_RANK[self.swarm.confidentiality_class] < vault_rank:
            raise PermissionError(
                "Swarm confidentiality is weaker than EmployerVault policy"
            )
        if (
            _VAULT_CLASSIFICATION_RANK[
                self.compute_requirement.confidentiality_class
            ]
            < vault_rank
        ):
            raise PermissionError(
                "ComputeRequirement confidentiality is weaker than EmployerVault policy"
            )
        if (
            _INVOCATION_CLASSIFICATION_RANK[
                self.invocation.data_classification
            ]
            < vault_rank
        ):
            raise PermissionError(
                "AgentInvocation classification is weaker than EmployerVault policy"
            )
        if not set(self.compute_requirement.allowed_jurisdictions).issubset(
            self.employer_vault.allowed_jurisdictions
        ):
            raise PermissionError(
                "ComputeRequirement jurisdiction scope exceeds EmployerVault policy"
            )

        required_scopes = {
            f"employer:{employer_id}",
            f"vault:{self.employer_vault.vault_id}",
            f"engagement:{self.engagement.engagement_id}",
            f"work_order:{self.work_order.work_order_id}",
            f"task:{task_id}",
        }
        if not required_scopes.issubset(self.invocation.authorization_scope):
            raise PermissionError(
                "AgentInvocation lacks canonical employer/work authorization scope"
            )

        observed_metadata = dict(self.invocation.metadata)
        for name, expected in self.metadata.items():
            if observed_metadata.get(name) != expected:
                raise PermissionError(
                    f"AgentInvocation canonical metadata mismatch: {name}"
                )

        if self.authorization.environment != self.invocation.environment.value:
            raise PermissionError(
                "Authorization environment does not match AgentInvocation"
            )
        if self.authorization.repository_tree_sha != observed_metadata[
            "repository_tree_sha"
        ]:
            raise PermissionError(
                "Authorization tree SHA does not match canonical metadata"
            )
        if self.authorization.schema_digest != self.invocation.schema_digest:
            raise PermissionError(
                "Authorization schema digest does not match AgentInvocation"
            )
        if not self.authorization.matches(
            action=REPOSITORY_ONLY_ACTION,
            target=self.work_order.work_order_id,
            repository_sha=observed_metadata["repository_sha"],
            idempotency_key_digest=observed_metadata[
                "idempotency_key_digest"
            ],
        ):
            raise PermissionError(
                "Authorization packet does not match the canonical WorkOrder"
            )
