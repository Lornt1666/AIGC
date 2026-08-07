from __future__ import annotations

from dataclasses import asdict, dataclass, is_dataclass
from datetime import datetime, timedelta
from enum import Enum
import hashlib
import json
from typing import Iterable, Mapping

from .compute_exchange import ComputeRequirement, ComputeStage
from .domain import (
    CapabilityEvidence,
    CapabilityVerdict,
    ConfidentialityClass,
    WorkOrder,
    _require_nonnegative,
    _require_text,
)
from .policy import EffectivePolicy, VaultDataScope


class TaskState(str, Enum):
    PLANNED = "PLANNED"
    READY = "READY"
    BLOCKED = "BLOCKED"
    EXECUTING = "EXECUTING"
    VERIFYING = "VERIFYING"
    COMPLETE = "COMPLETE"
    FAILED = "FAILED"
    CANCELLED = "CANCELLED"
    UNCERTAIN_EXTERNAL_OUTCOME = "UNCERTAIN_EXTERNAL_OUTCOME"


class QualificationStatus(str, Enum):
    ACTIVE = "ACTIVE"
    EXPIRED = "EXPIRED"
    REVOKED = "REVOKED"
    UNVERIFIED = "UNVERIFIED"


@dataclass(frozen=True)
class HumanQualificationEvidence:
    qualification_evidence_id: str
    human_identity_ref: str
    qualification_class: str
    issuing_authority: str
    jurisdiction: str
    valid_from: datetime
    valid_until: datetime
    status: QualificationStatus
    evidence_refs: tuple[str, ...]
    evidence_digest: str

    def __post_init__(self) -> None:
        for name in (
            "qualification_evidence_id",
            "human_identity_ref",
            "qualification_class",
            "issuing_authority",
            "jurisdiction",
        ):
            _require_text(name, getattr(self, name))
        if self.valid_from.tzinfo is None or self.valid_until.tzinfo is None:
            raise ValueError("qualification validity timestamps must be timezone-aware")
        if self.valid_until <= self.valid_from:
            raise ValueError("qualification valid_until must follow valid_from")
        if not self.evidence_refs:
            raise ValueError("qualification evidence requires evidence references")
        _require_sha256("evidence_digest", self.evidence_digest)

    def is_valid(self, *, as_of: datetime, allowed_jurisdictions: tuple[str, ...]) -> bool:
        return (
            self.status == QualificationStatus.ACTIVE
            and self.valid_from <= as_of < self.valid_until
            and self.jurisdiction in allowed_jurisdictions
        )


@dataclass(frozen=True)
class ProfessionalCredentialEvidence:
    credential_evidence_id: str
    human_identity_ref: str
    profession: str
    credential_class: str
    issuing_authority: str
    jurisdiction: str
    valid_from: datetime
    valid_until: datetime
    status: QualificationStatus
    evidence_refs: tuple[str, ...]
    evidence_digest: str

    def __post_init__(self) -> None:
        for name in (
            "credential_evidence_id",
            "human_identity_ref",
            "profession",
            "credential_class",
            "issuing_authority",
            "jurisdiction",
        ):
            _require_text(name, getattr(self, name))
        if self.valid_from.tzinfo is None or self.valid_until.tzinfo is None:
            raise ValueError("credential validity timestamps must be timezone-aware")
        if self.valid_until <= self.valid_from:
            raise ValueError("credential valid_until must follow valid_from")
        if not self.evidence_refs:
            raise ValueError("professional credential requires evidence references")
        _require_sha256("evidence_digest", self.evidence_digest)

    def is_valid(self, *, as_of: datetime, allowed_jurisdictions: tuple[str, ...]) -> bool:
        return (
            self.status == QualificationStatus.ACTIVE
            and self.valid_from <= as_of < self.valid_until
            and self.jurisdiction in allowed_jurisdictions
        )


@dataclass(frozen=True)
class CompletionCriterion:
    criterion_id: str
    description: str
    required: bool = True

    def __post_init__(self) -> None:
        _require_text("criterion_id", self.criterion_id)
        _require_text("description", self.description)


@dataclass(frozen=True)
class EvidenceRequirement:
    evidence_type: str
    description: str

    def __post_init__(self) -> None:
        _require_text("evidence_type", self.evidence_type)
        _require_text("description", self.description)


@dataclass(frozen=True)
class HumanReviewRequirement:
    required: bool
    licensed_reviewer_required: bool = False
    reviewer_qualification: str | None = None

    def __post_init__(self) -> None:
        if self.licensed_reviewer_required and not self.required:
            raise ValueError("licensed reviewer requirement implies human review")
        if self.licensed_reviewer_required and not self.reviewer_qualification:
            raise ValueError("licensed review requires reviewer_qualification")


@dataclass(frozen=True)
class DefinitionOfDone:
    definition_id: str
    work_order_id: str
    deliverable_type: str
    requirements: tuple[str, ...]
    acceptance_criteria: tuple[CompletionCriterion, ...]
    required_tests: tuple[str, ...]
    required_standards: tuple[str, ...]
    required_evidence: tuple[EvidenceRequirement, ...]
    required_verification: tuple[str, ...]
    human_review: HumanReviewRequirement
    minimum_quality: float
    completion_policy_version: str
    source_requirement_ids: tuple[str, ...] = ()
    source_acceptance_criterion_ids: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        for name in ("definition_id", "work_order_id", "deliverable_type", "completion_policy_version"):
            _require_text(name, getattr(self, name))
        if not self.requirements:
            raise ValueError("DefinitionOfDone requires requirements")
        if not self.acceptance_criteria:
            raise ValueError("DefinitionOfDone requires acceptance criteria")
        if not self.required_evidence:
            raise ValueError("DefinitionOfDone requires evidence requirements")
        if not self.source_requirement_ids:
            raise ValueError("DefinitionOfDone requires source requirement IDs")
        if not self.source_acceptance_criterion_ids:
            raise ValueError("DefinitionOfDone requires source acceptance criterion IDs")
        if not 0 <= self.minimum_quality <= 1:
            raise ValueError("minimum_quality must be between 0 and 1")

    def covers(self, work_order: WorkOrder) -> bool:
        return (
            set(work_order.requirement_ids).issubset(self.source_requirement_ids)
            and set(work_order.acceptance_criteria).issubset(self.source_acceptance_criterion_ids)
        )


@dataclass(frozen=True)
class Task:
    task_id: str
    work_order_id: str
    objective: str
    task_type: str
    required_capabilities: tuple[str, ...]
    input_artifact_ids: tuple[str, ...]
    expected_output_types: tuple[str, ...]
    definition_of_done_id: str
    estimated_effort_minutes: int
    parallelizable: bool
    external_effect: bool
    idempotency_required: bool
    human_review_required: bool
    deadline: datetime
    priority: int = 0
    state: TaskState = TaskState.PLANNED

    def __post_init__(self) -> None:
        for name in ("task_id", "work_order_id", "objective", "task_type", "definition_of_done_id"):
            _require_text(name, getattr(self, name))
        if not self.required_capabilities:
            raise ValueError("task requires capabilities")
        if not self.expected_output_types:
            raise ValueError("task requires expected outputs")
        _require_nonnegative("estimated_effort_minutes", self.estimated_effort_minutes)
        if self.estimated_effort_minutes == 0:
            raise ValueError("estimated_effort_minutes must be positive")
        if self.deadline.tzinfo is None:
            raise ValueError("task deadline must be timezone-aware")
        if self.external_effect and not self.idempotency_required:
            raise ValueError("external-effect task requires idempotency")


@dataclass(frozen=True)
class TaskDependency:
    predecessor_task_id: str
    successor_task_id: str

    def __post_init__(self) -> None:
        _require_text("predecessor_task_id", self.predecessor_task_id)
        _require_text("successor_task_id", self.successor_task_id)
        if self.predecessor_task_id == self.successor_task_id:
            raise ValueError("task cannot depend on itself")


@dataclass(frozen=True)
class TaskDAG:
    work_order_id: str
    tasks: tuple[Task, ...]
    dependencies: tuple[TaskDependency, ...] = ()

    def __post_init__(self) -> None:
        _require_text("work_order_id", self.work_order_id)
        if not self.tasks:
            raise ValueError("TaskDAG requires tasks")
        ids = [task.task_id for task in self.tasks]
        if len(ids) != len(set(ids)):
            raise ValueError("task IDs must be unique")
        if any(task.work_order_id != self.work_order_id for task in self.tasks):
            raise ValueError("task belongs to a different work order")
        known = set(ids)
        for dependency in self.dependencies:
            if dependency.predecessor_task_id not in known or dependency.successor_task_id not in known:
                raise ValueError("task dependency references unknown task")
        self.topological_order()

    def topological_order(self) -> tuple[str, ...]:
        task_ids = sorted(task.task_id for task in self.tasks)
        indegree = {task_id: 0 for task_id in task_ids}
        successors: dict[str, list[str]] = {task_id: [] for task_id in task_ids}
        for dependency in self.dependencies:
            indegree[dependency.successor_task_id] += 1
            successors[dependency.predecessor_task_id].append(dependency.successor_task_id)
        ready = sorted(task_id for task_id, degree in indegree.items() if degree == 0)
        result: list[str] = []
        while ready:
            current = ready.pop(0)
            result.append(current)
            for successor in sorted(successors[current]):
                indegree[successor] -= 1
                if indegree[successor] == 0:
                    ready.append(successor)
                    ready.sort()
        if len(result) != len(task_ids):
            raise ValueError("TaskDAG contains a cycle")
        return tuple(result)

    def ready_tasks(self, completed_task_ids: Iterable[str]) -> tuple[Task, ...]:
        completed = set(completed_task_ids)
        predecessor_map: dict[str, set[str]] = {task.task_id: set() for task in self.tasks}
        for dependency in self.dependencies:
            predecessor_map[dependency.successor_task_id].add(dependency.predecessor_task_id)
        return tuple(
            sorted(
                (
                    task
                    for task in self.tasks
                    if task.task_id not in completed
                    and predecessor_map[task.task_id].issubset(completed)
                ),
                key=lambda task: (-task.priority, task.task_id),
            )
        )

    def blocked_task_ids(self, completed_task_ids: Iterable[str]) -> tuple[str, ...]:
        ready_ids = {task.task_id for task in self.ready_tasks(completed_task_ids)}
        completed = set(completed_task_ids)
        return tuple(
            sorted(task.task_id for task in self.tasks if task.task_id not in completed | ready_ids)
        )

    def critical_path_minutes(self) -> int:
        tasks = {task.task_id: task for task in self.tasks}
        predecessors: dict[str, list[str]] = {task_id: [] for task_id in tasks}
        for dependency in self.dependencies:
            predecessors[dependency.successor_task_id].append(dependency.predecessor_task_id)
        longest: dict[str, int] = {}
        for task_id in self.topological_order():
            longest[task_id] = (
                max((longest[p] for p in predecessors[task_id]), default=0)
                + tasks[task_id].estimated_effort_minutes
            )
        return max(longest.values())


@dataclass(frozen=True)
class AgentRoleDefinition:
    role_id: str
    capabilities: tuple[str, ...]
    allowed_tools: tuple[str, ...]
    allowed_data_scopes: tuple[VaultDataScope, ...]
    maximum_cost_cad: float
    maximum_tokens: int
    qualified_human: bool = False
    licensed_specialist: bool = False
    human_identity_ref: str | None = None
    maximum_compute_seconds: int = 0

    def __post_init__(self) -> None:
        _require_text("role_id", self.role_id)
        if not self.capabilities:
            raise ValueError("agent role requires capabilities")
        if any(not isinstance(scope, VaultDataScope) for scope in self.allowed_data_scopes):
            raise TypeError("agent role data scopes must be VaultDataScope objects")
        _require_nonnegative("maximum_cost_cad", self.maximum_cost_cad)
        _require_nonnegative("maximum_tokens", self.maximum_tokens)
        _require_nonnegative("maximum_compute_seconds", self.maximum_compute_seconds)
        if (self.qualified_human or self.licensed_specialist) and not self.human_identity_ref:
            raise ValueError("qualified human roles require human_identity_ref")


@dataclass(frozen=True)
class CapabilityMatch:
    capability: str
    evidence_id: str
    verdict: CapabilityVerdict


@dataclass(frozen=True)
class AgentAssignment:
    task_id: str
    role_id: str
    capability_matches: tuple[CapabilityMatch, ...]
    qualification_evidence_refs: tuple[str, ...]
    allowed_tools: tuple[str, ...]
    allowed_data_scopes: tuple[VaultDataScope, ...]
    maximum_cost_cad: float
    maximum_tokens: int
    maximum_compute_seconds: int
    human_review_required: bool
    execution_authorized: bool = False

    def __post_init__(self) -> None:
        _require_text("task_id", self.task_id)
        _require_text("role_id", self.role_id)
        _require_nonnegative("maximum_cost_cad", self.maximum_cost_cad)
        _require_nonnegative("maximum_tokens", self.maximum_tokens)
        _require_nonnegative("maximum_compute_seconds", self.maximum_compute_seconds)
        if self.execution_authorized:
            raise ValueError("orchestration-kernel V1 cannot authorize execution")


@dataclass(frozen=True)
class VerificationAssignment:
    task_id: str
    builder_role_id: str
    verifier_role_id: str
    verifier_capability_matches: tuple[CapabilityMatch, ...]
    qualification_evidence_refs: tuple[str, ...]
    verification_checks: tuple[str, ...]
    evidence_required: bool
    human_review_required: bool
    licensed_review_required: bool
    maximum_cost_cad: float
    maximum_tokens: int
    maximum_compute_seconds: int
    compute_requirement_id: str
    independence_required: bool = True

    def __post_init__(self) -> None:
        if self.independence_required and self.builder_role_id == self.verifier_role_id:
            raise ValueError("builder cannot self-certify when verifier independence is required")
        if not self.verifier_capability_matches:
            raise ValueError("verifier selection requires capability evidence")
        if not self.verification_checks:
            raise ValueError("verification assignment requires checks")
        if self.licensed_review_required and not self.qualification_evidence_refs:
            raise ValueError("licensed review requires qualification evidence")
        _require_nonnegative("maximum_cost_cad", self.maximum_cost_cad)
        _require_nonnegative("maximum_tokens", self.maximum_tokens)
        _require_nonnegative("maximum_compute_seconds", self.maximum_compute_seconds)
        _require_text("compute_requirement_id", self.compute_requirement_id)


@dataclass(frozen=True)
class VerificationPlan:
    work_order_id: str
    assignments: tuple[VerificationAssignment, ...]

    def __post_init__(self) -> None:
        _require_text("work_order_id", self.work_order_id)
        if not self.assignments:
            raise ValueError("verification plan requires assignments")


@dataclass(frozen=True)
class SchedulingDecision:
    decision_id: str
    task_id: str
    inputs_digest: str
    input_snapshot_schema_version: str
    scheduler_version: str
    candidate_roles: tuple[str, ...]
    selected_role: str
    rejected_roles: tuple[str, ...]
    reason_codes: tuple[str, ...]
    policy_refs: tuple[str, ...]
    capability_evidence_refs: tuple[str, ...]
    qualification_evidence_refs: tuple[str, ...]

    def __post_init__(self) -> None:
        for name in (
            "decision_id",
            "task_id",
            "input_snapshot_schema_version",
            "scheduler_version",
            "selected_role",
        ):
            _require_text(name, getattr(self, name))
        _require_sha256("inputs_digest", self.inputs_digest)


@dataclass(frozen=True)
class SwarmPlan:
    plan_id: str
    work_order_id: str
    employer_policy_id: str
    task_order: tuple[str, ...]
    assignments: tuple[AgentAssignment, ...]
    verification_plan: VerificationPlan
    compute_requirements: tuple[ComputeRequirement, ...]
    scheduling_decisions: tuple[SchedulingDecision, ...]
    maximum_cost_cad: float
    maximum_tokens: int
    maximum_compute_seconds: int
    execution_authorized: bool = False

    def __post_init__(self) -> None:
        if self.execution_authorized:
            raise ValueError("orchestration-kernel V1 produces plans only")
        _require_nonnegative("maximum_cost_cad", self.maximum_cost_cad)
        _require_nonnegative("maximum_tokens", self.maximum_tokens)
        _require_nonnegative("maximum_compute_seconds", self.maximum_compute_seconds)
        total_cost = sum(a.maximum_cost_cad for a in self.assignments) + sum(
            a.maximum_cost_cad for a in self.verification_plan.assignments
        )
        total_tokens = sum(a.maximum_tokens for a in self.assignments) + sum(
            a.maximum_tokens for a in self.verification_plan.assignments
        )
        total_compute = sum(a.maximum_compute_seconds for a in self.assignments) + sum(
            a.maximum_compute_seconds for a in self.verification_plan.assignments
        )
        if total_cost > self.maximum_cost_cad + 1e-9:
            raise ValueError("builder and verifier budgets exceed plan cost ceiling")
        if total_tokens > self.maximum_tokens:
            raise ValueError("builder and verifier token maxima exceed plan token budget")
        if total_compute > self.maximum_compute_seconds:
            raise ValueError("builder and verifier compute reservations exceed plan limit")


class SwarmScheduler:
    VERSION = "1.1.0"
    INPUT_SNAPSHOT_SCHEMA_VERSION = "1.0.0"

    def plan(
        self,
        *,
        work_order: WorkOrder,
        dag: TaskDAG,
        effective_policy: EffectivePolicy,
        definitions_of_done: tuple[DefinitionOfDone, ...],
        capability_evidence: tuple[CapabilityEvidence, ...],
        roles: tuple[AgentRoleDefinition, ...],
        as_of: datetime,
        human_qualification_evidence: tuple[HumanQualificationEvidence, ...] = (),
        professional_credentials: tuple[ProfessionalCredentialEvidence, ...] = (),
    ) -> SwarmPlan:
        if as_of.tzinfo is None:
            raise ValueError("as_of must be timezone-aware")
        if work_order.work_order_id != dag.work_order_id:
            raise ValueError("work order and TaskDAG do not match")
        if not work_order.authorized:
            raise ValueError("work order must be authorized before planning")
        definitions = {definition.definition_id: definition for definition in definitions_of_done}
        evidence_by_skill: dict[str, list[CapabilityEvidence]] = {}
        for evidence in capability_evidence:
            evidence_by_skill.setdefault(evidence.skill, []).append(evidence)
        if len({role.role_id for role in roles}) != len(roles):
            raise ValueError("role IDs must be unique")

        assignments: list[AgentAssignment] = []
        verifications: list[VerificationAssignment] = []
        requirements: list[ComputeRequirement] = []
        decisions: list[SchedulingDecision] = []
        task_order = dag.topological_order()
        task_map = {task.task_id: task for task in dag.tasks}
        task_count = len(task_order)

        for task_id in task_order:
            task = task_map[task_id]
            if task.deadline <= as_of:
                raise ValueError(f"task {task.task_id} deadline has expired")
            definition = definitions.get(task.definition_of_done_id)
            if definition is None or definition.work_order_id != work_order.work_order_id:
                raise ValueError(f"task {task.task_id} has no valid DefinitionOfDone")
            if not definition.covers(work_order):
                raise ValueError(f"task {task.task_id} DefinitionOfDone omits WorkOrder obligations")

            eligible: list[
                tuple[
                    AgentRoleDefinition,
                    tuple[CapabilityMatch, ...],
                    bool,
                    tuple[str, ...],
                ]
            ] = []
            rejected: list[str] = []
            for role in sorted(roles, key=lambda candidate: candidate.role_id):
                try:
                    matches, review_required, qualification_refs = self._match_role(
                        task=task,
                        role=role,
                        evidence_by_skill=evidence_by_skill,
                        effective_policy=effective_policy,
                        as_of=as_of,
                        human_qualification_evidence=human_qualification_evidence,
                        professional_credentials=professional_credentials,
                    )
                    self._validate_role_policy(role, effective_policy)
                    eligible.append((role, matches, review_required, qualification_refs))
                except ValueError:
                    rejected.append(role.role_id)
            if not eligible:
                raise ValueError(f"no eligible agent role for task {task.task_id}")

            role, matches, review_required, qualification_refs = eligible[0]
            allowed_tools = self._effective_allowed_values(role.allowed_tools, effective_policy.allowed_tools)
            allowed_data_scopes = self._effective_scopes(role.allowed_data_scopes, effective_policy)
            task_cost_pool = effective_policy.maximum_cost_cad / task_count
            task_token_pool = effective_policy.maximum_token_budget // task_count
            task_compute_pool = effective_policy.maximum_compute_seconds // task_count
            builder_cost_cap = min(role.maximum_cost_cad, task_cost_pool * 0.65)
            builder_token_cap = min(role.maximum_tokens, int(task_token_pool * 0.65))
            builder_compute_cap = min(
                role.maximum_compute_seconds or task_compute_pool,
                int(task_compute_pool * 0.65),
            )

            external_review_required = (
                task.external_effect and effective_policy.review_required_for_external_effects
            )
            restricted_review_required = (
                effective_policy.review_required_for_restricted_work
                and (
                    effective_policy.minimum_confidentiality_class == ConfidentialityClass.RESTRICTED
                    or any(match.verdict == CapabilityVerdict.LEGALLY_RESTRICTED for match in matches)
                )
            )
            human_review_required = (
                task.human_review_required
                or review_required
                or external_review_required
                or restricted_review_required
            )
            assignments.append(
                AgentAssignment(
                    task.task_id,
                    role.role_id,
                    matches,
                    qualification_refs,
                    allowed_tools,
                    allowed_data_scopes,
                    builder_cost_cap,
                    builder_token_cap,
                    builder_compute_cap,
                    human_review_required,
                )
            )

            verifier, verifier_matches, verifier_qualification_refs = self._select_verifier(
                builder_role_id=role.role_id,
                roles=roles,
                effective_policy=effective_policy,
                evidence_by_skill=evidence_by_skill,
                as_of=as_of,
                human_qualification_evidence=human_qualification_evidence,
                professional_credentials=professional_credentials,
                require_licensed=(
                    definition.human_review.licensed_reviewer_required
                    or any(match.verdict == CapabilityVerdict.LEGALLY_RESTRICTED for match in matches)
                ),
            )
            verification_cost_cap = min(verifier.maximum_cost_cad, task_cost_pool - builder_cost_cap)
            verification_token_cap = min(
                verifier.maximum_tokens,
                max(0, task_token_pool - builder_token_cap),
            )
            verification_compute_cap = min(
                verifier.maximum_compute_seconds or task_compute_pool,
                max(0, task_compute_pool - builder_compute_cap),
            )
            checks = tuple(
                sorted(
                    set(definition.required_tests)
                    | set(definition.required_standards)
                    | set(definition.required_verification)
                )
            ) or ("acceptance-criteria",)
            verification_requirement_id = f"compute-verify-{task.task_id}"
            licensed_review_required = (
                definition.human_review.licensed_reviewer_required
                or any(match.verdict == CapabilityVerdict.LEGALLY_RESTRICTED for match in matches)
            )
            verifications.append(
                VerificationAssignment(
                    task.task_id,
                    role.role_id,
                    verifier.role_id,
                    verifier_matches,
                    verifier_qualification_refs,
                    checks,
                    effective_policy.evidence_required,
                    human_review_required,
                    licensed_review_required,
                    verification_cost_cap,
                    verification_token_cap,
                    verification_compute_cap,
                    verification_requirement_id,
                    effective_policy.independent_verification_required,
                )
            )

            remaining_ms = max(0, int((task.deadline - as_of).total_seconds() * 1000))
            policy_ms = int(effective_policy.maximum_task_duration.total_seconds() * 1000)
            maximum_latency_ms = min(policy_ms, remaining_ms)
            if maximum_latency_ms <= 0:
                raise ValueError(f"task {task.task_id} has no feasible execution window")

            requirements.extend(
                (
                    self._compute_requirement(
                        requirement_id=f"compute-build-{task.task_id}",
                        work_order=work_order,
                        task=task,
                        stage=ComputeStage.BUILD,
                        minimum_quality=definition.minimum_quality,
                        maximum_latency_ms=maximum_latency_ms,
                        maximum_cost_cad=builder_cost_cap,
                        maximum_compute_seconds=builder_compute_cap,
                        effective_policy=effective_policy,
                        required_capabilities=task.required_capabilities,
                        allowed_tools=allowed_tools,
                    ),
                    self._compute_requirement(
                        requirement_id=verification_requirement_id,
                        work_order=work_order,
                        task=task,
                        stage=ComputeStage.VERIFY,
                        minimum_quality=definition.minimum_quality,
                        maximum_latency_ms=maximum_latency_ms,
                        maximum_cost_cad=verification_cost_cap,
                        maximum_compute_seconds=verification_compute_cap,
                        effective_policy=effective_policy,
                        required_capabilities=tuple(
                            sorted(match.capability for match in verifier_matches)
                        ),
                        allowed_tools=self._effective_allowed_values(
                            verifier.allowed_tools, effective_policy.allowed_tools
                        ),
                    ),
                )
            )

            decision_snapshot = {
                "schema_version": self.INPUT_SNAPSHOT_SCHEMA_VERSION,
                "scheduler_version": self.VERSION,
                "as_of": as_of,
                "work_order": work_order,
                "task_dag": dag,
                "task": task,
                "definition_of_done": definition,
                "effective_policy": effective_policy,
                "candidate_roles": tuple(sorted(roles, key=lambda item: item.role_id)),
                "capability_evidence": tuple(
                    sorted(capability_evidence, key=lambda item: item.capability_evidence_id)
                ),
                "human_qualification_evidence": tuple(
                    sorted(
                        human_qualification_evidence,
                        key=lambda item: item.qualification_evidence_id,
                    )
                ),
                "professional_credentials": tuple(
                    sorted(
                        professional_credentials,
                        key=lambda item: item.credential_evidence_id,
                    )
                ),
                "selected_builder_role_id": role.role_id,
                "selected_verifier_role_id": verifier.role_id,
            }
            decision_digest = canonical_sha256(decision_snapshot)
            decisions.append(
                SchedulingDecision(
                    f"decision-{task.task_id}",
                    task.task_id,
                    decision_digest,
                    self.INPUT_SNAPSHOT_SCHEMA_VERSION,
                    self.VERSION,
                    tuple(candidate.role_id for candidate, *_ in eligible),
                    role.role_id,
                    tuple(sorted(rejected)),
                    (
                        "DETERMINISTIC_FIRST_ELIGIBLE",
                        "CAPABILITY_EVIDENCE_BOUND",
                        "VERIFIER_EVIDENCE_BOUND",
                        "POLICY_BOUND",
                        "FULL_INPUT_DIGEST",
                    ),
                    (effective_policy.policy_id,),
                    tuple(
                        sorted(
                            {match.evidence_id for match in matches}
                            | {match.evidence_id for match in verifier_matches}
                        )
                    ),
                    tuple(sorted(set(qualification_refs) | set(verifier_qualification_refs))),
                )
            )

        return SwarmPlan(
            f"swarm-plan-{work_order.work_order_id}",
            work_order.work_order_id,
            effective_policy.policy_id,
            task_order,
            tuple(assignments),
            VerificationPlan(work_order.work_order_id, tuple(verifications)),
            tuple(requirements),
            tuple(decisions),
            effective_policy.maximum_cost_cad,
            effective_policy.maximum_token_budget,
            effective_policy.maximum_compute_seconds,
        )

    @staticmethod
    def _match_role(
        *,
        task: Task,
        role: AgentRoleDefinition,
        evidence_by_skill: Mapping[str, list[CapabilityEvidence]],
        effective_policy: EffectivePolicy,
        as_of: datetime,
        human_qualification_evidence: tuple[HumanQualificationEvidence, ...],
        professional_credentials: tuple[ProfessionalCredentialEvidence, ...],
    ) -> tuple[tuple[CapabilityMatch, ...], bool, tuple[str, ...]]:
        if not set(task.required_capabilities).issubset(role.capabilities):
            raise ValueError("role lacks required capabilities")
        matches: list[CapabilityMatch] = []
        review_required = False
        qualification_refs: set[str] = set()
        for capability in task.required_capabilities:
            evidence = _select_capability_evidence(evidence_by_skill.get(capability, []))
            if evidence is None:
                raise ValueError("missing capability evidence")
            if evidence.verdict in {
                CapabilityVerdict.NOT_QUALIFIED,
                CapabilityVerdict.RESEARCH_REQUIRED,
            }:
                raise ValueError("capability is not currently assignable")
            if evidence.verdict == CapabilityVerdict.LEGALLY_RESTRICTED:
                credential = _valid_professional_credential(
                    role=role,
                    as_of=as_of,
                    allowed_jurisdictions=effective_policy.allowed_jurisdictions,
                    credentials=professional_credentials,
                )
                if credential is None:
                    raise ValueError("legally restricted capability requires valid credential evidence")
                qualification_refs.add(credential.credential_evidence_id)
            if evidence.verdict == CapabilityVerdict.CAPABLE_WITH_SPECIALIST:
                qualification = _valid_human_qualification(
                    role=role,
                    as_of=as_of,
                    allowed_jurisdictions=effective_policy.allowed_jurisdictions,
                    evidence=human_qualification_evidence,
                )
                if qualification is None:
                    raise ValueError("capability requires qualified specialist evidence")
                qualification_refs.add(qualification.qualification_evidence_id)
            if evidence.verdict == CapabilityVerdict.CAPABLE_WITH_REVIEW or evidence.human_review_required:
                review_required = True
            matches.append(
                CapabilityMatch(
                    capability,
                    evidence.capability_evidence_id,
                    evidence.verdict,
                )
            )
        return tuple(matches), review_required, tuple(sorted(qualification_refs))

    @staticmethod
    def _validate_role_policy(role: AgentRoleDefinition, effective_policy: EffectivePolicy) -> None:
        if set(role.allowed_tools) & set(effective_policy.prohibited_tools):
            raise ValueError("role uses prohibited tool")
        if effective_policy.allowed_tools and not set(role.allowed_tools).issubset(
            effective_policy.allowed_tools
        ):
            raise ValueError("role uses tool outside effective allowlist")
        policy_scopes = {scope.scope_id: scope for scope in effective_policy.allowed_data_scopes}
        for scope in role.allowed_data_scopes:
            expected = policy_scopes.get(scope.scope_id)
            if expected is None or expected != scope:
                raise ValueError("role requests data outside employer vault policy")
            if scope.vault_id != effective_policy.vault_id or scope.employer_id != effective_policy.employer_id:
                raise ValueError("role data scope crosses employer-vault boundary")

    @staticmethod
    def _effective_allowed_values(
        role_values: tuple[str, ...], policy_values: tuple[str, ...]
    ) -> tuple[str, ...]:
        return (
            tuple(sorted(set(role_values) & set(policy_values)))
            if policy_values
            else tuple(sorted(set(role_values)))
        )

    @staticmethod
    def _effective_scopes(
        role_scopes: tuple[VaultDataScope, ...],
        effective_policy: EffectivePolicy,
    ) -> tuple[VaultDataScope, ...]:
        allowed = {scope.scope_id: scope for scope in effective_policy.allowed_data_scopes}
        result = tuple(
            sorted(
                (
                    scope
                    for scope in role_scopes
                    if allowed.get(scope.scope_id) == scope
                    and scope.vault_id == effective_policy.vault_id
                    and scope.employer_id == effective_policy.employer_id
                ),
                key=lambda scope: scope.scope_id,
            )
        )
        if not result:
            raise ValueError("role has no employer-authorized data scope")
        return result

    @staticmethod
    def _select_verifier(
        *,
        builder_role_id: str,
        roles: tuple[AgentRoleDefinition, ...],
        effective_policy: EffectivePolicy,
        evidence_by_skill: Mapping[str, list[CapabilityEvidence]],
        as_of: datetime,
        human_qualification_evidence: tuple[HumanQualificationEvidence, ...],
        professional_credentials: tuple[ProfessionalCredentialEvidence, ...],
        require_licensed: bool,
    ) -> tuple[AgentRoleDefinition, tuple[CapabilityMatch, ...], tuple[str, ...]]:
        for role in sorted(roles, key=lambda candidate: candidate.role_id):
            if effective_policy.independent_verification_required and role.role_id == builder_role_id:
                continue
            verification_capabilities = tuple(
                capability
                for capability in ("verification", "review")
                if capability in role.capabilities
            )
            if not verification_capabilities:
                continue
            try:
                SwarmScheduler._validate_role_policy(role, effective_policy)
            except ValueError:
                continue
            matches: list[CapabilityMatch] = []
            for capability in verification_capabilities:
                evidence = _select_capability_evidence(evidence_by_skill.get(capability, []))
                if evidence is None or evidence.verdict in {
                    CapabilityVerdict.NOT_QUALIFIED,
                    CapabilityVerdict.RESEARCH_REQUIRED,
                }:
                    continue
                matches.append(
                    CapabilityMatch(
                        capability,
                        evidence.capability_evidence_id,
                        evidence.verdict,
                    )
                )
            if not matches:
                continue
            qualification_refs: set[str] = set()
            if require_licensed:
                credential = _valid_professional_credential(
                    role=role,
                    as_of=as_of,
                    allowed_jurisdictions=effective_policy.allowed_jurisdictions,
                    credentials=professional_credentials,
                )
                if credential is None:
                    continue
                qualification_refs.add(credential.credential_evidence_id)
            return role, tuple(matches), tuple(sorted(qualification_refs))
        raise ValueError("no evidence-bound independent verifier satisfies policy")

    @staticmethod
    def _compute_requirement(
        *,
        requirement_id: str,
        work_order: WorkOrder,
        task: Task,
        stage: ComputeStage,
        minimum_quality: float,
        maximum_latency_ms: int,
        maximum_cost_cad: float,
        maximum_compute_seconds: int,
        effective_policy: EffectivePolicy,
        required_capabilities: tuple[str, ...],
        allowed_tools: tuple[str, ...],
    ) -> ComputeRequirement:
        return ComputeRequirement(
            requirement_id=requirement_id,
            work_order_id=work_order.work_order_id,
            task_id=task.task_id,
            stage=stage,
            workload_class=task.task_type,
            minimum_quality=minimum_quality,
            minimum_reliability=0.90,
            minimum_availability=0.95,
            minimum_security_level=effective_policy.minimum_security_level,
            minimum_privacy_level=effective_policy.minimum_privacy_level,
            maximum_latency_ms=maximum_latency_ms,
            maximum_cost_cad=maximum_cost_cad,
            maximum_compute_seconds=maximum_compute_seconds,
            confidentiality_class=effective_policy.minimum_confidentiality_class,
            allowed_jurisdictions=effective_policy.allowed_jurisdictions,
            allowed_providers=effective_policy.allowed_providers,
            prohibited_providers=effective_policy.prohibited_providers,
            allowed_models=effective_policy.allowed_models,
            prohibited_models=effective_policy.prohibited_models,
            allowed_tools=allowed_tools,
            prohibited_tools=effective_policy.prohibited_tools,
            external_api_allowed=effective_policy.external_api_allowed,
            open_source_allowed=effective_policy.open_source_allowed,
            cross_border_allowed=effective_policy.cross_border_allowed,
            external_training_use_allowed=effective_policy.external_training_use_allowed,
            required_capabilities=required_capabilities,
        )


def _select_capability_evidence(
    options: Iterable[CapabilityEvidence],
) -> CapabilityEvidence | None:
    sorted_options = sorted(
        options,
        key=lambda item: (item.last_verified_at, item.capability_evidence_id),
        reverse=True,
    )
    return sorted_options[0] if sorted_options else None


def _valid_human_qualification(
    *,
    role: AgentRoleDefinition,
    as_of: datetime,
    allowed_jurisdictions: tuple[str, ...],
    evidence: tuple[HumanQualificationEvidence, ...],
) -> HumanQualificationEvidence | None:
    if not role.qualified_human or not role.human_identity_ref:
        return None
    matches = [
        item
        for item in evidence
        if item.human_identity_ref == role.human_identity_ref
        and item.is_valid(as_of=as_of, allowed_jurisdictions=allowed_jurisdictions)
    ]
    return sorted(matches, key=lambda item: item.qualification_evidence_id)[0] if matches else None


def _valid_professional_credential(
    *,
    role: AgentRoleDefinition,
    as_of: datetime,
    allowed_jurisdictions: tuple[str, ...],
    credentials: tuple[ProfessionalCredentialEvidence, ...],
) -> ProfessionalCredentialEvidence | None:
    if not role.licensed_specialist or not role.human_identity_ref:
        return None
    matches = [
        item
        for item in credentials
        if item.human_identity_ref == role.human_identity_ref
        and item.is_valid(as_of=as_of, allowed_jurisdictions=allowed_jurisdictions)
    ]
    return sorted(matches, key=lambda item: item.credential_evidence_id)[0] if matches else None


def canonical_sha256(value: object) -> str:
    return hashlib.sha256(canonical_json(value).encode("utf-8")).hexdigest()


def canonical_json(value: object) -> str:
    return json.dumps(
        _canonicalize(value),
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    )


def _canonicalize(value: object) -> object:
    if is_dataclass(value):
        return _canonicalize(asdict(value))
    if isinstance(value, Enum):
        return value.value
    if isinstance(value, datetime):
        return value.isoformat()
    if isinstance(value, timedelta):
        return value.total_seconds()
    if isinstance(value, Mapping):
        return {
            str(key): _canonicalize(item)
            for key, item in sorted(value.items(), key=lambda pair: str(pair[0]))
        }
    if isinstance(value, (tuple, list)):
        return [_canonicalize(item) for item in value]
    if isinstance(value, set):
        return sorted(_canonicalize(item) for item in value)
    return value


def _require_sha256(name: str, value: str) -> None:
    if len(value) != 64 or any(character not in "0123456789abcdef" for character in value.lower()):
        raise ValueError(f"{name} must be a 64-character hexadecimal SHA-256 digest")
