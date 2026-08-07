from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
import hashlib
import json
from typing import Iterable

from .compute_exchange import ComputeRequirement
from .domain import (
    CapabilityEvidence,
    CapabilityVerdict,
    ConfidentialityClass,
    WorkOrder,
    _require_nonnegative,
    _require_text,
)
from .policy import EffectivePolicy


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

    def __post_init__(self) -> None:
        for name in ("definition_id", "work_order_id", "deliverable_type", "completion_policy_version"):
            _require_text(name, getattr(self, name))
        if not self.requirements:
            raise ValueError("DefinitionOfDone requires requirements")
        if not self.acceptance_criteria:
            raise ValueError("DefinitionOfDone requires acceptance criteria")
        if not self.required_evidence:
            raise ValueError("DefinitionOfDone requires evidence requirements")
        if not 0 <= self.minimum_quality <= 1:
            raise ValueError("minimum_quality must be between 0 and 1")


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
                    if task.task_id not in completed and predecessor_map[task.task_id].issubset(completed)
                ),
                key=lambda task: (-task.priority, task.task_id),
            )
        )

    def blocked_task_ids(self, completed_task_ids: Iterable[str]) -> tuple[str, ...]:
        ready_ids = {task.task_id for task in self.ready_tasks(completed_task_ids)}
        completed = set(completed_task_ids)
        return tuple(sorted(task.task_id for task in self.tasks if task.task_id not in completed | ready_ids))

    def critical_path_minutes(self) -> int:
        tasks = {task.task_id: task for task in self.tasks}
        predecessors: dict[str, list[str]] = {task_id: [] for task_id in tasks}
        for dependency in self.dependencies:
            predecessors[dependency.successor_task_id].append(dependency.predecessor_task_id)
        longest: dict[str, int] = {}
        for task_id in self.topological_order():
            prior = max((longest[p] for p in predecessors[task_id]), default=0)
            longest[task_id] = prior + tasks[task_id].estimated_effort_minutes
        return max(longest.values())


@dataclass(frozen=True)
class AgentRoleDefinition:
    role_id: str
    capabilities: tuple[str, ...]
    allowed_tools: tuple[str, ...]
    allowed_data_scopes: tuple[str, ...]
    maximum_cost_cad: float
    maximum_tokens: int
    qualified_human: bool = False
    licensed_specialist: bool = False

    def __post_init__(self) -> None:
        _require_text("role_id", self.role_id)
        if not self.capabilities:
            raise ValueError("agent role requires capabilities")
        _require_nonnegative("maximum_cost_cad", self.maximum_cost_cad)
        _require_nonnegative("maximum_tokens", self.maximum_tokens)


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
    allowed_tools: tuple[str, ...]
    allowed_data_scopes: tuple[str, ...]
    maximum_cost_cad: float
    maximum_tokens: int
    human_review_required: bool
    execution_authorized: bool = False

    def __post_init__(self) -> None:
        _require_text("task_id", self.task_id)
        _require_text("role_id", self.role_id)
        if self.execution_authorized:
            raise ValueError("orchestration-kernel V1 cannot authorize execution")


@dataclass(frozen=True)
class VerificationAssignment:
    task_id: str
    builder_role_id: str
    verifier_role_id: str
    verification_checks: tuple[str, ...]
    evidence_required: bool
    human_review_required: bool
    licensed_review_required: bool
    independence_required: bool = True

    def __post_init__(self) -> None:
        if self.independence_required and self.builder_role_id == self.verifier_role_id:
            raise ValueError("builder cannot self-certify when verifier independence is required")
        if not self.verification_checks:
            raise ValueError("verification assignment requires checks")


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
    scheduler_version: str
    candidate_roles: tuple[str, ...]
    selected_role: str
    rejected_roles: tuple[str, ...]
    reason_codes: tuple[str, ...]
    policy_refs: tuple[str, ...]
    capability_evidence_refs: tuple[str, ...]


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
    execution_authorized: bool = False

    def __post_init__(self) -> None:
        if self.execution_authorized:
            raise ValueError("orchestration-kernel V1 produces plans only")
        _require_nonnegative("maximum_cost_cad", self.maximum_cost_cad)
        _require_nonnegative("maximum_tokens", self.maximum_tokens)
        if sum(a.maximum_cost_cad for a in self.assignments) > self.maximum_cost_cad:
            raise ValueError("agent assignment budgets exceed plan budget")
        if sum(a.maximum_tokens for a in self.assignments) > self.maximum_tokens:
            raise ValueError("agent assignment token maxima exceed plan token budget")


class SwarmScheduler:
    VERSION = "1.0.0"

    def plan(
        self,
        *,
        work_order: WorkOrder,
        dag: TaskDAG,
        effective_policy: EffectivePolicy,
        definitions_of_done: tuple[DefinitionOfDone, ...],
        capability_evidence: tuple[CapabilityEvidence, ...],
        roles: tuple[AgentRoleDefinition, ...],
    ) -> SwarmPlan:
        if work_order.work_order_id != dag.work_order_id:
            raise ValueError("work order and TaskDAG do not match")
        if not work_order.authorized:
            raise ValueError("work order must be authorized before planning")

        definitions = {definition.definition_id: definition for definition in definitions_of_done}
        evidence_by_skill: dict[str, list[CapabilityEvidence]] = {}
        for evidence in capability_evidence:
            evidence_by_skill.setdefault(evidence.skill, []).append(evidence)
        role_map = {role.role_id: role for role in roles}
        if len(role_map) != len(roles):
            raise ValueError("role IDs must be unique")

        assignments: list[AgentAssignment] = []
        verifications: list[VerificationAssignment] = []
        requirements: list[ComputeRequirement] = []
        decisions: list[SchedulingDecision] = []

        task_order = dag.topological_order()
        task_map = {task.task_id: task for task in dag.tasks}
        for task_id in task_order:
            task = task_map[task_id]
            definition = definitions.get(task.definition_of_done_id)
            if definition is None or definition.work_order_id != work_order.work_order_id:
                raise ValueError(f"task {task.task_id} has no valid DefinitionOfDone")

            eligible: list[tuple[AgentRoleDefinition, tuple[CapabilityMatch, ...], bool]] = []
            rejected: list[str] = []
            for role in sorted(roles, key=lambda candidate: candidate.role_id):
                try:
                    matches, review_required = self._match_role(task, role, evidence_by_skill)
                    self._validate_role_policy(role, effective_policy)
                    eligible.append((role, matches, review_required))
                except ValueError:
                    rejected.append(role.role_id)

            if not eligible:
                raise ValueError(f"no eligible agent role for task {task.task_id}")

            role, matches, review_required = eligible[0]
            allowed_tools = self._effective_allowed_values(role.allowed_tools, effective_policy.allowed_tools)
            allowed_data_scopes = tuple(
                sorted(set(role.allowed_data_scopes) & set(effective_policy.employer_policy.data.allowed_data_scopes))
            )
            if not allowed_data_scopes:
                raise ValueError(f"role {role.role_id} has no employer-authorized data scope")

            cost_cap = min(role.maximum_cost_cad, effective_policy.employer_policy.maximum_cost_cad)
            token_cap = min(role.maximum_tokens, effective_policy.employer_policy.maximum_token_budget)
            assignments.append(
                AgentAssignment(
                    task_id=task.task_id,
                    role_id=role.role_id,
                    capability_matches=matches,
                    allowed_tools=allowed_tools,
                    allowed_data_scopes=allowed_data_scopes,
                    maximum_cost_cad=cost_cap,
                    maximum_tokens=token_cap,
                    human_review_required=(task.human_review_required or review_required),
                )
            )

            verifier = self._select_verifier(
                builder_role_id=role.role_id,
                roles=roles,
                effective_policy=effective_policy,
                require_licensed=definition.human_review.licensed_reviewer_required,
            )
            verifications.append(
                VerificationAssignment(
                    task_id=task.task_id,
                    builder_role_id=role.role_id,
                    verifier_role_id=verifier.role_id,
                    verification_checks=tuple(
                        sorted(
                            set(definition.required_tests)
                            | set(definition.required_standards)
                            | set(definition.required_verification)
                        )
                    ) or ("acceptance-criteria",),
                    evidence_required=effective_policy.evidence_required,
                    human_review_required=(definition.human_review.required or review_required),
                    licensed_review_required=definition.human_review.licensed_reviewer_required,
                    independence_required=effective_policy.independent_verification_required,
                )
            )

            requirements.append(
                ComputeRequirement(
                    requirement_id=f"compute-{task.task_id}",
                    workload_class=task.task_type,
                    minimum_quality=definition.minimum_quality,
                    minimum_reliability=0.90,
                    minimum_availability=0.95,
                    minimum_security_level=effective_policy.minimum_security_level,
                    minimum_privacy_level=effective_policy.minimum_privacy_level,
                    maximum_latency_ms=int(effective_policy.employer_policy.maximum_task_duration.total_seconds() * 1000),
                    maximum_cost_cad=cost_cap,
                    confidentiality_class=effective_policy.minimum_confidentiality_class,
                    allowed_jurisdictions=effective_policy.allowed_jurisdictions,
                    allowed_providers=effective_policy.allowed_providers,
                    required_capabilities=task.required_capabilities,
                )
            )

            digest = self._decision_digest(work_order, task, role, effective_policy.policy_id)
            decisions.append(
                SchedulingDecision(
                    decision_id=f"decision-{task.task_id}",
                    task_id=task.task_id,
                    inputs_digest=digest,
                    scheduler_version=self.VERSION,
                    candidate_roles=tuple(candidate.role_id for candidate, _, _ in eligible),
                    selected_role=role.role_id,
                    rejected_roles=tuple(sorted(rejected)),
                    reason_codes=("DETERMINISTIC_FIRST_ELIGIBLE", "CAPABILITY_EVIDENCE_BOUND", "POLICY_BOUND"),
                    policy_refs=(effective_policy.employer_policy.policy_id,),
                    capability_evidence_refs=tuple(sorted(match.evidence_id for match in matches)),
                )
            )

        verification_plan = VerificationPlan(work_order_id=work_order.work_order_id, assignments=tuple(verifications))
        return SwarmPlan(
            plan_id=f"swarm-plan-{work_order.work_order_id}",
            work_order_id=work_order.work_order_id,
            employer_policy_id=effective_policy.employer_policy.policy_id,
            task_order=task_order,
            assignments=tuple(assignments),
            verification_plan=verification_plan,
            compute_requirements=tuple(requirements),
            scheduling_decisions=tuple(decisions),
            maximum_cost_cad=effective_policy.employer_policy.maximum_cost_cad,
            maximum_tokens=effective_policy.employer_policy.maximum_token_budget,
        )

    @staticmethod
    def _match_role(
        task: Task,
        role: AgentRoleDefinition,
        evidence_by_skill: dict[str, list[CapabilityEvidence]],
    ) -> tuple[tuple[CapabilityMatch, ...], bool]:
        if not set(task.required_capabilities).issubset(role.capabilities):
            raise ValueError("role lacks required capabilities")
        matches: list[CapabilityMatch] = []
        review_required = False
        for capability in task.required_capabilities:
            evidence_options = sorted(
                evidence_by_skill.get(capability, []),
                key=lambda item: item.capability_evidence_id,
            )
            if not evidence_options:
                raise ValueError("missing capability evidence")
            evidence = evidence_options[0]
            if evidence.verdict in {CapabilityVerdict.NOT_QUALIFIED, CapabilityVerdict.RESEARCH_REQUIRED}:
                raise ValueError("capability is not currently assignable")
            if evidence.verdict == CapabilityVerdict.LEGALLY_RESTRICTED and not role.licensed_specialist:
                raise ValueError("legally restricted capability requires licensed specialist")
            if evidence.verdict == CapabilityVerdict.CAPABLE_WITH_SPECIALIST and not role.qualified_human:
                raise ValueError("capability requires specialist participation")
            if evidence.verdict == CapabilityVerdict.CAPABLE_WITH_REVIEW or evidence.human_review_required:
                review_required = True
            matches.append(
                CapabilityMatch(
                    capability=capability,
                    evidence_id=evidence.capability_evidence_id,
                    verdict=evidence.verdict,
                )
            )
        return tuple(matches), review_required

    @staticmethod
    def _validate_role_policy(role: AgentRoleDefinition, effective_policy: EffectivePolicy) -> None:
        if effective_policy.allowed_tools and not set(role.allowed_tools).issubset(effective_policy.allowed_tools):
            raise ValueError("role uses tool outside effective policy")
        if not set(role.allowed_data_scopes).issubset(effective_policy.employer_policy.data.allowed_data_scopes):
            raise ValueError("role requests data outside employer vault policy")

    @staticmethod
    def _effective_allowed_values(role_values: tuple[str, ...], policy_values: tuple[str, ...]) -> tuple[str, ...]:
        if policy_values:
            return tuple(sorted(set(role_values) & set(policy_values)))
        return tuple(sorted(set(role_values)))

    @staticmethod
    def _select_verifier(
        *,
        builder_role_id: str,
        roles: tuple[AgentRoleDefinition, ...],
        effective_policy: EffectivePolicy,
        require_licensed: bool,
    ) -> AgentRoleDefinition:
        candidates = []
        for role in sorted(roles, key=lambda candidate: candidate.role_id):
            if effective_policy.independent_verification_required and role.role_id == builder_role_id:
                continue
            if require_licensed and not role.licensed_specialist:
                continue
            if "verification" not in role.capabilities and "review" not in role.capabilities:
                continue
            try:
                SwarmScheduler._validate_role_policy(role, effective_policy)
            except ValueError:
                continue
            candidates.append(role)
        if not candidates:
            raise ValueError("no independent verifier satisfies policy")
        return candidates[0]

    @staticmethod
    def _decision_digest(work_order: WorkOrder, task: Task, role: AgentRoleDefinition, policy_id: str) -> str:
        payload = {
            "work_order_id": work_order.work_order_id,
            "task_id": task.task_id,
            "role_id": role.role_id,
            "policy_id": policy_id,
            "required_capabilities": list(task.required_capabilities),
        }
        return hashlib.sha256(json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()).hexdigest()
