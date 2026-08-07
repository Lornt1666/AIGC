from __future__ import annotations

from datetime import datetime, timedelta
from typing import Any

from .compute_exchange import ComputeRequirement, ComputeStage
from .domain import CapabilityVerdict, ConfidentialityClass
from .orchestration import (
    AgentAssignment,
    CapabilityMatch,
    CompletionCriterion,
    DefinitionOfDone,
    EvidenceRequirement,
    HumanQualificationEvidence,
    HumanReviewRequirement,
    ProfessionalCredentialEvidence,
    QualificationStatus,
    SchedulingDecision,
    SwarmPlan,
    Task,
    TaskDAG,
    TaskDependency,
    TaskState,
    VerificationAssignment,
    VerificationPlan,
    canonical_sha256,
)
from .policy import (
    ConfidentialityPolicy,
    DataPolicy,
    EffectivePolicy,
    EmployerPolicy,
    HumanReviewPolicy,
    JurisdictionPolicy,
    ModelPolicy,
    RetentionPolicy,
    SecurityPolicy,
    ToolPolicy,
    VaultDataScope,
    VerificationPolicy,
)


def scope_record(scope: VaultDataScope) -> dict[str, object]:
    return {
        "scope_id": scope.scope_id,
        "vault_id": scope.vault_id,
        "employer_id": scope.employer_id,
        "classification": scope.classification.value,
        "purpose": scope.purpose,
    }


def scope_from_record(record: dict[str, Any]) -> VaultDataScope:
    return VaultDataScope(
        scope_id=str(record["scope_id"]),
        vault_id=str(record["vault_id"]),
        employer_id=str(record["employer_id"]),
        classification=ConfidentialityClass(str(record["classification"])),
        purpose=str(record["purpose"]),
    )


def employer_policy_record(policy: EmployerPolicy) -> dict[str, object]:
    return {
        "policy_id": policy.policy_id,
        "employer_id": policy.employer_id,
        "vault_id": policy.vault_id,
        "engagement_id": policy.engagement_id,
        "allowed_jurisdictions": list(policy.jurisdiction.allowed_jurisdictions),
        "prohibited_jurisdictions": list(policy.jurisdiction.prohibited_jurisdictions),
        "cross_border_allowed": policy.jurisdiction.cross_border_allowed,
        "allowed_providers": list(policy.models.allowed_providers),
        "prohibited_providers": list(policy.models.prohibited_providers),
        "allowed_models": list(policy.models.allowed_models),
        "prohibited_models": list(policy.models.prohibited_models),
        "allowed_tools": list(policy.tools.allowed_tools),
        "prohibited_tools": list(policy.tools.prohibited_tools),
        "external_api_allowed": policy.tools.external_api_allowed,
        "open_source_allowed": policy.tools.open_source_allowed,
        "confidentiality_class": policy.confidentiality.minimum_class.value,
        "external_training_use_allowed": policy.confidentiality.external_training_use_allowed,
        "allowed_data_scopes": [scope_record(scope) for scope in policy.data.allowed_data_scopes],
        "cross_employer_retrieval_allowed": policy.data.cross_employer_retrieval_allowed,
        "cross_employer_prompt_context_allowed": policy.data.cross_employer_prompt_context_allowed,
        "retention_days": policy.retention.retention_days,
        "deletion_required_after_retention": policy.retention.deletion_required_after_retention,
        "review_required_for_external_effects": policy.human_review.review_required_for_external_effects,
        "review_required_for_restricted_work": policy.human_review.review_required_for_restricted_work,
        "licensed_review_required_when_legally_restricted": (
            policy.human_review.licensed_review_required_when_legally_restricted
        ),
        "minimum_security_level": policy.security.minimum_security_level,
        "minimum_privacy_level": policy.security.minimum_privacy_level,
        "independent_verification_required": policy.verification.independent_verification_required,
        "evidence_required": policy.verification.evidence_required,
        "maximum_cost_cad": policy.maximum_cost_cad,
        "maximum_token_budget": policy.maximum_token_budget,
        "maximum_compute_seconds": policy.maximum_compute_seconds,
        "maximum_task_duration_seconds": int(policy.maximum_task_duration.total_seconds()),
    }


def employer_policy_from_record(record: dict[str, Any]) -> EmployerPolicy:
    return EmployerPolicy(
        policy_id=str(record["policy_id"]),
        employer_id=str(record["employer_id"]),
        vault_id=str(record["vault_id"]),
        engagement_id=str(record["engagement_id"]),
        jurisdiction=JurisdictionPolicy(
            tuple(record["allowed_jurisdictions"]),
            tuple(record["prohibited_jurisdictions"]),
            bool(record["cross_border_allowed"]),
        ),
        confidentiality=ConfidentialityPolicy(
            ConfidentialityClass(str(record["confidentiality_class"])),
            False,
            bool(record["external_training_use_allowed"]),
        ),
        tools=ToolPolicy(
            tuple(record["allowed_tools"]),
            tuple(record["prohibited_tools"]),
            bool(record["external_api_allowed"]),
            bool(record["open_source_allowed"]),
        ),
        models=ModelPolicy(
            tuple(record["allowed_models"]),
            tuple(record["prohibited_models"]),
            tuple(record["allowed_providers"]),
            tuple(record["prohibited_providers"]),
        ),
        data=DataPolicy(
            str(record["vault_id"]),
            str(record["employer_id"]),
            tuple(scope_from_record(item) for item in record["allowed_data_scopes"]),
            bool(record["cross_employer_retrieval_allowed"]),
            bool(record["cross_employer_prompt_context_allowed"]),
        ),
        retention=RetentionPolicy(
            int(record["retention_days"]),
            bool(record["deletion_required_after_retention"]),
        ),
        human_review=HumanReviewPolicy(
            bool(record["review_required_for_external_effects"]),
            bool(record["review_required_for_restricted_work"]),
            bool(record["licensed_review_required_when_legally_restricted"]),
        ),
        security=SecurityPolicy(
            int(record["minimum_security_level"]),
            int(record["minimum_privacy_level"]),
        ),
        verification=VerificationPolicy(
            bool(record["independent_verification_required"]),
            bool(record["evidence_required"]),
        ),
        maximum_cost_cad=float(record["maximum_cost_cad"]),
        maximum_token_budget=int(record["maximum_token_budget"]),
        maximum_compute_seconds=int(record["maximum_compute_seconds"]),
        maximum_task_duration=timedelta(
            seconds=int(record["maximum_task_duration_seconds"])
        ),
    )


def effective_policy_record(policy: EffectivePolicy) -> dict[str, object]:
    return {
        "employer_policy": employer_policy_record(policy.employer_policy),
        "allowed_jurisdictions": list(policy.allowed_jurisdictions),
        "prohibited_jurisdictions": list(policy.prohibited_jurisdictions),
        "cross_border_allowed": policy.cross_border_allowed,
        "allowed_tools": list(policy.allowed_tools),
        "prohibited_tools": list(policy.prohibited_tools),
        "external_api_allowed": policy.external_api_allowed,
        "open_source_allowed": policy.open_source_allowed,
        "allowed_models": list(policy.allowed_models),
        "prohibited_models": list(policy.prohibited_models),
        "allowed_providers": list(policy.allowed_providers),
        "prohibited_providers": list(policy.prohibited_providers),
        "minimum_confidentiality_class": policy.minimum_confidentiality_class.value,
        "external_training_use_allowed": policy.external_training_use_allowed,
        "allowed_data_scopes": [scope_record(scope) for scope in policy.allowed_data_scopes],
        "retention_days": policy.retention_days,
        "deletion_required_after_retention": policy.deletion_required_after_retention,
        "minimum_security_level": policy.minimum_security_level,
        "minimum_privacy_level": policy.minimum_privacy_level,
        "review_required_for_external_effects": policy.review_required_for_external_effects,
        "review_required_for_restricted_work": policy.review_required_for_restricted_work,
        "licensed_review_required_when_legally_restricted": (
            policy.licensed_review_required_when_legally_restricted
        ),
        "independent_verification_required": policy.independent_verification_required,
        "evidence_required": policy.evidence_required,
        "maximum_cost_cad": policy.maximum_cost_cad,
        "maximum_token_budget": policy.maximum_token_budget,
        "maximum_compute_seconds": policy.maximum_compute_seconds,
        "maximum_task_duration_seconds": int(policy.maximum_task_duration.total_seconds()),
    }


def effective_policy_from_record(record: dict[str, Any]) -> EffectivePolicy:
    return EffectivePolicy(
        employer_policy=employer_policy_from_record(record["employer_policy"]),
        allowed_jurisdictions=tuple(record["allowed_jurisdictions"]),
        prohibited_jurisdictions=tuple(record["prohibited_jurisdictions"]),
        cross_border_allowed=bool(record["cross_border_allowed"]),
        allowed_tools=tuple(record["allowed_tools"]),
        prohibited_tools=tuple(record["prohibited_tools"]),
        external_api_allowed=bool(record["external_api_allowed"]),
        open_source_allowed=bool(record["open_source_allowed"]),
        allowed_models=tuple(record["allowed_models"]),
        prohibited_models=tuple(record["prohibited_models"]),
        allowed_providers=tuple(record["allowed_providers"]),
        prohibited_providers=tuple(record["prohibited_providers"]),
        minimum_confidentiality_class=ConfidentialityClass(
            str(record["minimum_confidentiality_class"])
        ),
        external_training_use_allowed=bool(record["external_training_use_allowed"]),
        allowed_data_scopes=tuple(
            scope_from_record(item) for item in record["allowed_data_scopes"]
        ),
        retention_days=int(record["retention_days"]),
        deletion_required_after_retention=bool(record["deletion_required_after_retention"]),
        minimum_security_level=int(record["minimum_security_level"]),
        minimum_privacy_level=int(record["minimum_privacy_level"]),
        review_required_for_external_effects=bool(
            record["review_required_for_external_effects"]
        ),
        review_required_for_restricted_work=bool(
            record["review_required_for_restricted_work"]
        ),
        licensed_review_required_when_legally_restricted=bool(
            record["licensed_review_required_when_legally_restricted"]
        ),
        independent_verification_required=bool(
            record["independent_verification_required"]
        ),
        evidence_required=bool(record["evidence_required"]),
        maximum_cost_cad=float(record["maximum_cost_cad"]),
        maximum_token_budget=int(record["maximum_token_budget"]),
        maximum_compute_seconds=int(record["maximum_compute_seconds"]),
        maximum_task_duration=timedelta(
            seconds=int(record["maximum_task_duration_seconds"])
        ),
    )


def definition_of_done_record(definition: DefinitionOfDone) -> dict[str, object]:
    return {
        "definition_id": definition.definition_id,
        "work_order_id": definition.work_order_id,
        "deliverable_type": definition.deliverable_type,
        "requirements": list(definition.requirements),
        "source_requirement_ids": list(definition.source_requirement_ids),
        "acceptance_criteria": [
            {
                "criterion_id": item.criterion_id,
                "description": item.description,
                "required": item.required,
            }
            for item in definition.acceptance_criteria
        ],
        "source_acceptance_criterion_ids": list(
            definition.source_acceptance_criterion_ids
        ),
        "required_tests": list(definition.required_tests),
        "required_standards": list(definition.required_standards),
        "required_evidence": [
            {
                "evidence_type": item.evidence_type,
                "description": item.description,
            }
            for item in definition.required_evidence
        ],
        "required_verification": list(definition.required_verification),
        "human_review_required": definition.human_review.required,
        "licensed_review_required": definition.human_review.licensed_reviewer_required,
        "reviewer_qualification": definition.human_review.reviewer_qualification,
        "minimum_quality": definition.minimum_quality,
        "completion_policy_version": definition.completion_policy_version,
    }


def definition_of_done_from_record(record: dict[str, Any]) -> DefinitionOfDone:
    return DefinitionOfDone(
        definition_id=str(record["definition_id"]),
        work_order_id=str(record["work_order_id"]),
        deliverable_type=str(record["deliverable_type"]),
        requirements=tuple(record["requirements"]),
        acceptance_criteria=tuple(
            CompletionCriterion(
                str(item["criterion_id"]),
                str(item["description"]),
                bool(item["required"]),
            )
            for item in record["acceptance_criteria"]
        ),
        required_tests=tuple(record["required_tests"]),
        required_standards=tuple(record["required_standards"]),
        required_evidence=tuple(
            EvidenceRequirement(str(item["evidence_type"]), str(item["description"]))
            for item in record["required_evidence"]
        ),
        required_verification=tuple(record["required_verification"]),
        human_review=HumanReviewRequirement(
            bool(record["human_review_required"]),
            bool(record["licensed_review_required"]),
            record.get("reviewer_qualification"),
        ),
        minimum_quality=float(record["minimum_quality"]),
        completion_policy_version=str(record["completion_policy_version"]),
        source_requirement_ids=tuple(record["source_requirement_ids"]),
        source_acceptance_criterion_ids=tuple(
            record["source_acceptance_criterion_ids"]
        ),
    )


def task_dag_record(dag: TaskDAG) -> dict[str, object]:
    return {
        "work_order_id": dag.work_order_id,
        "tasks": [
            {
                "task_id": task.task_id,
                "work_order_id": task.work_order_id,
                "objective": task.objective,
                "task_type": task.task_type,
                "required_capabilities": list(task.required_capabilities),
                "input_artifact_ids": list(task.input_artifact_ids),
                "expected_output_types": list(task.expected_output_types),
                "definition_of_done_id": task.definition_of_done_id,
                "estimated_effort_minutes": task.estimated_effort_minutes,
                "parallelizable": task.parallelizable,
                "external_effect": task.external_effect,
                "idempotency_required": task.idempotency_required,
                "human_review_required": task.human_review_required,
                "deadline": task.deadline.isoformat(),
                "priority": task.priority,
                "state": task.state.value,
            }
            for task in dag.tasks
        ],
        "dependencies": [
            {
                "predecessor_task_id": dependency.predecessor_task_id,
                "successor_task_id": dependency.successor_task_id,
            }
            for dependency in dag.dependencies
        ],
    }


def task_dag_from_record(record: dict[str, Any]) -> TaskDAG:
    return TaskDAG(
        work_order_id=str(record["work_order_id"]),
        tasks=tuple(
            Task(
                task_id=str(item["task_id"]),
                work_order_id=str(item["work_order_id"]),
                objective=str(item["objective"]),
                task_type=str(item["task_type"]),
                required_capabilities=tuple(item["required_capabilities"]),
                input_artifact_ids=tuple(item["input_artifact_ids"]),
                expected_output_types=tuple(item["expected_output_types"]),
                definition_of_done_id=str(item["definition_of_done_id"]),
                estimated_effort_minutes=int(item["estimated_effort_minutes"]),
                parallelizable=bool(item["parallelizable"]),
                external_effect=bool(item["external_effect"]),
                idempotency_required=bool(item["idempotency_required"]),
                human_review_required=bool(item["human_review_required"]),
                deadline=datetime.fromisoformat(str(item["deadline"])),
                priority=int(item["priority"]),
                state=TaskState(str(item["state"])),
            )
            for item in record["tasks"]
        ),
        dependencies=tuple(
            TaskDependency(
                str(item["predecessor_task_id"]),
                str(item["successor_task_id"]),
            )
            for item in record["dependencies"]
        ),
    )


def capability_match_record(match: CapabilityMatch) -> dict[str, object]:
    return {
        "capability": match.capability,
        "evidence_id": match.evidence_id,
        "verdict": match.verdict.value,
    }


def capability_match_from_record(record: dict[str, Any]) -> CapabilityMatch:
    return CapabilityMatch(
        str(record["capability"]),
        str(record["evidence_id"]),
        CapabilityVerdict(str(record["verdict"])),
    )


def compute_requirement_record(requirement: ComputeRequirement) -> dict[str, object]:
    return {
        "requirement_id": requirement.requirement_id,
        "work_order_id": requirement.work_order_id,
        "task_id": requirement.task_id,
        "stage": requirement.stage.value,
        "workload_class": requirement.workload_class,
        "minimum_quality": requirement.minimum_quality,
        "minimum_reliability": requirement.minimum_reliability,
        "minimum_availability": requirement.minimum_availability,
        "minimum_security_level": requirement.minimum_security_level,
        "minimum_privacy_level": requirement.minimum_privacy_level,
        "maximum_latency_ms": requirement.maximum_latency_ms,
        "maximum_cost_cad": requirement.maximum_cost_cad,
        "maximum_compute_seconds": requirement.maximum_compute_seconds,
        "confidentiality_class": requirement.confidentiality_class.value,
        "allowed_jurisdictions": list(requirement.allowed_jurisdictions),
        "allowed_providers": list(requirement.allowed_providers),
        "prohibited_providers": list(requirement.prohibited_providers),
        "allowed_models": list(requirement.allowed_models),
        "prohibited_models": list(requirement.prohibited_models),
        "allowed_tools": list(requirement.allowed_tools),
        "prohibited_tools": list(requirement.prohibited_tools),
        "external_api_allowed": requirement.external_api_allowed,
        "open_source_allowed": requirement.open_source_allowed,
        "cross_border_allowed": requirement.cross_border_allowed,
        "external_training_use_allowed": requirement.external_training_use_allowed,
        "required_capabilities": list(requirement.required_capabilities),
        "license_must_allow_commercial_use": requirement.license_must_allow_commercial_use,
    }


def compute_requirement_from_record(record: dict[str, Any]) -> ComputeRequirement:
    return ComputeRequirement(
        requirement_id=str(record["requirement_id"]),
        work_order_id=str(record["work_order_id"]),
        task_id=str(record["task_id"]),
        stage=ComputeStage(str(record["stage"])),
        workload_class=str(record["workload_class"]),
        minimum_quality=float(record["minimum_quality"]),
        minimum_reliability=float(record["minimum_reliability"]),
        minimum_availability=float(record["minimum_availability"]),
        minimum_security_level=int(record["minimum_security_level"]),
        minimum_privacy_level=int(record["minimum_privacy_level"]),
        maximum_latency_ms=int(record["maximum_latency_ms"]),
        maximum_cost_cad=float(record["maximum_cost_cad"]),
        maximum_compute_seconds=int(record["maximum_compute_seconds"]),
        confidentiality_class=ConfidentialityClass(str(record["confidentiality_class"])),
        allowed_jurisdictions=tuple(record["allowed_jurisdictions"]),
        allowed_providers=tuple(record["allowed_providers"]),
        prohibited_providers=tuple(record["prohibited_providers"]),
        allowed_models=tuple(record["allowed_models"]),
        prohibited_models=tuple(record["prohibited_models"]),
        allowed_tools=tuple(record["allowed_tools"]),
        prohibited_tools=tuple(record["prohibited_tools"]),
        external_api_allowed=bool(record["external_api_allowed"]),
        open_source_allowed=bool(record["open_source_allowed"]),
        cross_border_allowed=bool(record["cross_border_allowed"]),
        external_training_use_allowed=bool(record["external_training_use_allowed"]),
        required_capabilities=tuple(record["required_capabilities"]),
        license_must_allow_commercial_use=bool(
            record["license_must_allow_commercial_use"]
        ),
    )


def verification_plan_record(plan: VerificationPlan) -> dict[str, object]:
    return {
        "work_order_id": plan.work_order_id,
        "assignments": [
            {
                "task_id": item.task_id,
                "builder_role_id": item.builder_role_id,
                "verifier_role_id": item.verifier_role_id,
                "verifier_capability_matches": [
                    capability_match_record(match)
                    for match in item.verifier_capability_matches
                ],
                "qualification_evidence_refs": list(item.qualification_evidence_refs),
                "verification_checks": list(item.verification_checks),
                "evidence_required": item.evidence_required,
                "human_review_required": item.human_review_required,
                "licensed_review_required": item.licensed_review_required,
                "maximum_cost_cad": item.maximum_cost_cad,
                "maximum_tokens": item.maximum_tokens,
                "maximum_compute_seconds": item.maximum_compute_seconds,
                "compute_requirement_id": item.compute_requirement_id,
                "independence_required": item.independence_required,
            }
            for item in plan.assignments
        ],
    }


def verification_plan_from_record(record: dict[str, Any]) -> VerificationPlan:
    return VerificationPlan(
        work_order_id=str(record["work_order_id"]),
        assignments=tuple(
            VerificationAssignment(
                task_id=str(item["task_id"]),
                builder_role_id=str(item["builder_role_id"]),
                verifier_role_id=str(item["verifier_role_id"]),
                verifier_capability_matches=tuple(
                    capability_match_from_record(match)
                    for match in item["verifier_capability_matches"]
                ),
                qualification_evidence_refs=tuple(
                    item["qualification_evidence_refs"]
                ),
                verification_checks=tuple(item["verification_checks"]),
                evidence_required=bool(item["evidence_required"]),
                human_review_required=bool(item["human_review_required"]),
                licensed_review_required=bool(item["licensed_review_required"]),
                maximum_cost_cad=float(item["maximum_cost_cad"]),
                maximum_tokens=int(item["maximum_tokens"]),
                maximum_compute_seconds=int(item["maximum_compute_seconds"]),
                compute_requirement_id=str(item["compute_requirement_id"]),
                independence_required=bool(item["independence_required"]),
            )
            for item in record["assignments"]
        ),
    )


def scheduling_decision_record(decision: SchedulingDecision) -> dict[str, object]:
    return {
        "decision_id": decision.decision_id,
        "task_id": decision.task_id,
        "inputs_digest": decision.inputs_digest,
        "input_snapshot_schema_version": decision.input_snapshot_schema_version,
        "scheduler_version": decision.scheduler_version,
        "candidate_roles": list(decision.candidate_roles),
        "selected_role": decision.selected_role,
        "rejected_roles": list(decision.rejected_roles),
        "reason_codes": list(decision.reason_codes),
        "policy_refs": list(decision.policy_refs),
        "capability_evidence_refs": list(decision.capability_evidence_refs),
        "qualification_evidence_refs": list(decision.qualification_evidence_refs),
    }


def scheduling_decision_from_record(record: dict[str, Any]) -> SchedulingDecision:
    return SchedulingDecision(
        decision_id=str(record["decision_id"]),
        task_id=str(record["task_id"]),
        inputs_digest=str(record["inputs_digest"]),
        input_snapshot_schema_version=str(record["input_snapshot_schema_version"]),
        scheduler_version=str(record["scheduler_version"]),
        candidate_roles=tuple(record["candidate_roles"]),
        selected_role=str(record["selected_role"]),
        rejected_roles=tuple(record["rejected_roles"]),
        reason_codes=tuple(record["reason_codes"]),
        policy_refs=tuple(record["policy_refs"]),
        capability_evidence_refs=tuple(record["capability_evidence_refs"]),
        qualification_evidence_refs=tuple(record["qualification_evidence_refs"]),
    )


def swarm_plan_record(plan: SwarmPlan) -> dict[str, object]:
    record: dict[str, object] = {
        "plan_id": plan.plan_id,
        "work_order_id": plan.work_order_id,
        "employer_policy_id": plan.employer_policy_id,
        "task_order": list(plan.task_order),
        "assignments": [
            {
                "task_id": item.task_id,
                "role_id": item.role_id,
                "capability_matches": [
                    capability_match_record(match) for match in item.capability_matches
                ],
                "qualification_evidence_refs": list(item.qualification_evidence_refs),
                "allowed_tools": list(item.allowed_tools),
                "allowed_data_scopes": [
                    scope_record(scope) for scope in item.allowed_data_scopes
                ],
                "maximum_cost_cad": item.maximum_cost_cad,
                "maximum_tokens": item.maximum_tokens,
                "maximum_compute_seconds": item.maximum_compute_seconds,
                "human_review_required": item.human_review_required,
                "execution_authorized": item.execution_authorized,
            }
            for item in plan.assignments
        ],
        "verification_plan": verification_plan_record(plan.verification_plan),
        "compute_requirements": [
            compute_requirement_record(item) for item in plan.compute_requirements
        ],
        "scheduling_decisions": [
            scheduling_decision_record(item) for item in plan.scheduling_decisions
        ],
        "maximum_cost_cad": plan.maximum_cost_cad,
        "maximum_tokens": plan.maximum_tokens,
        "maximum_compute_seconds": plan.maximum_compute_seconds,
        "execution_authorized": plan.execution_authorized,
    }
    record["record_sha256"] = canonical_sha256(record)
    return record


def swarm_plan_from_record(record: dict[str, Any]) -> SwarmPlan:
    source = dict(record)
    expected_digest = source.pop("record_sha256", None)
    if expected_digest is not None and canonical_sha256(source) != expected_digest:
        raise ValueError("SwarmPlan record digest mismatch")
    return SwarmPlan(
        plan_id=str(source["plan_id"]),
        work_order_id=str(source["work_order_id"]),
        employer_policy_id=str(source["employer_policy_id"]),
        task_order=tuple(source["task_order"]),
        assignments=tuple(
            AgentAssignment(
                task_id=str(item["task_id"]),
                role_id=str(item["role_id"]),
                capability_matches=tuple(
                    capability_match_from_record(match)
                    for match in item["capability_matches"]
                ),
                qualification_evidence_refs=tuple(
                    item["qualification_evidence_refs"]
                ),
                allowed_tools=tuple(item["allowed_tools"]),
                allowed_data_scopes=tuple(
                    scope_from_record(scope) for scope in item["allowed_data_scopes"]
                ),
                maximum_cost_cad=float(item["maximum_cost_cad"]),
                maximum_tokens=int(item["maximum_tokens"]),
                maximum_compute_seconds=int(item["maximum_compute_seconds"]),
                human_review_required=bool(item["human_review_required"]),
                execution_authorized=bool(item["execution_authorized"]),
            )
            for item in source["assignments"]
        ),
        verification_plan=verification_plan_from_record(source["verification_plan"]),
        compute_requirements=tuple(
            compute_requirement_from_record(item)
            for item in source["compute_requirements"]
        ),
        scheduling_decisions=tuple(
            scheduling_decision_from_record(item)
            for item in source["scheduling_decisions"]
        ),
        maximum_cost_cad=float(source["maximum_cost_cad"]),
        maximum_tokens=int(source["maximum_tokens"]),
        maximum_compute_seconds=int(source["maximum_compute_seconds"]),
        execution_authorized=bool(source["execution_authorized"]),
    )


def human_qualification_record(
    evidence: HumanQualificationEvidence,
) -> dict[str, object]:
    return {
        "qualification_evidence_id": evidence.qualification_evidence_id,
        "human_identity_ref": evidence.human_identity_ref,
        "qualification_class": evidence.qualification_class,
        "issuing_authority": evidence.issuing_authority,
        "jurisdiction": evidence.jurisdiction,
        "valid_from": evidence.valid_from.isoformat(),
        "valid_until": evidence.valid_until.isoformat(),
        "status": evidence.status.value,
        "evidence_refs": list(evidence.evidence_refs),
        "evidence_digest": evidence.evidence_digest,
    }


def human_qualification_from_record(
    record: dict[str, Any],
) -> HumanQualificationEvidence:
    return HumanQualificationEvidence(
        qualification_evidence_id=str(record["qualification_evidence_id"]),
        human_identity_ref=str(record["human_identity_ref"]),
        qualification_class=str(record["qualification_class"]),
        issuing_authority=str(record["issuing_authority"]),
        jurisdiction=str(record["jurisdiction"]),
        valid_from=datetime.fromisoformat(str(record["valid_from"])),
        valid_until=datetime.fromisoformat(str(record["valid_until"])),
        status=QualificationStatus(str(record["status"])),
        evidence_refs=tuple(record["evidence_refs"]),
        evidence_digest=str(record["evidence_digest"]),
    )


def professional_credential_record(
    evidence: ProfessionalCredentialEvidence,
) -> dict[str, object]:
    return {
        "credential_evidence_id": evidence.credential_evidence_id,
        "human_identity_ref": evidence.human_identity_ref,
        "profession": evidence.profession,
        "credential_class": evidence.credential_class,
        "issuing_authority": evidence.issuing_authority,
        "jurisdiction": evidence.jurisdiction,
        "valid_from": evidence.valid_from.isoformat(),
        "valid_until": evidence.valid_until.isoformat(),
        "status": evidence.status.value,
        "evidence_refs": list(evidence.evidence_refs),
        "evidence_digest": evidence.evidence_digest,
    }


def professional_credential_from_record(
    record: dict[str, Any],
) -> ProfessionalCredentialEvidence:
    return ProfessionalCredentialEvidence(
        credential_evidence_id=str(record["credential_evidence_id"]),
        human_identity_ref=str(record["human_identity_ref"]),
        profession=str(record["profession"]),
        credential_class=str(record["credential_class"]),
        issuing_authority=str(record["issuing_authority"]),
        jurisdiction=str(record["jurisdiction"]),
        valid_from=datetime.fromisoformat(str(record["valid_from"])),
        valid_until=datetime.fromisoformat(str(record["valid_until"])),
        status=QualificationStatus(str(record["status"])),
        evidence_refs=tuple(record["evidence_refs"]),
        evidence_digest=str(record["evidence_digest"]),
    )


def orchestration_bundle_record(
    *,
    effective_policy: EffectivePolicy,
    definitions_of_done: tuple[DefinitionOfDone, ...],
    task_dag: TaskDAG,
    swarm_plan: SwarmPlan,
    human_qualifications: tuple[HumanQualificationEvidence, ...] = (),
    professional_credentials: tuple[ProfessionalCredentialEvidence, ...] = (),
) -> dict[str, object]:
    record: dict[str, object] = {
        "schema_version": "1.0.0",
        "effective_policy": effective_policy_record(effective_policy),
        "definitions_of_done": [
            definition_of_done_record(item) for item in definitions_of_done
        ],
        "task_dag": task_dag_record(task_dag),
        "swarm_plan": swarm_plan_record(swarm_plan),
        "human_qualifications": [
            human_qualification_record(item) for item in human_qualifications
        ],
        "professional_credentials": [
            professional_credential_record(item) for item in professional_credentials
        ],
        "authority": {
            "execution_authorized": False,
            "external_action_authorized": False,
            "merge_authorized": False,
            "deployment_authorized": False,
            "live_model_call_authorized": False,
            "financial_action_authorized": False,
        },
    }
    record["record_sha256"] = canonical_sha256(record)
    return record


def assert_round_trip(
    record: dict[str, Any],
    *,
    loader,
    dumper,
) -> None:
    reconstructed = loader(record)
    if dumper(reconstructed) != record:
        raise ValueError("canonical persistence round trip lost information")
