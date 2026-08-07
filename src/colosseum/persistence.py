from __future__ import annotations

from .orchestration import DefinitionOfDone, SwarmPlan, TaskDAG, VerificationPlan
from .policy import EmployerPolicy


def employer_policy_record(policy: EmployerPolicy) -> dict[str, object]:
    return {
        "policy_id": policy.policy_id,
        "employer_id": policy.employer_id,
        "vault_id": policy.vault_id,
        "engagement_id": policy.engagement_id,
        "allowed_jurisdictions": list(policy.jurisdiction.allowed_jurisdictions),
        "prohibited_jurisdictions": list(policy.jurisdiction.prohibited_jurisdictions),
        "allowed_providers": list(policy.models.allowed_providers),
        "prohibited_providers": list(policy.models.prohibited_providers),
        "allowed_models": list(policy.models.allowed_models),
        "prohibited_models": list(policy.models.prohibited_models),
        "allowed_tools": list(policy.tools.allowed_tools),
        "prohibited_tools": list(policy.tools.prohibited_tools),
        "confidentiality_class": policy.confidentiality.minimum_class.value,
        "allowed_data_scopes": list(policy.data.allowed_data_scopes),
        "maximum_cost_cad": policy.maximum_cost_cad,
        "maximum_token_budget": policy.maximum_token_budget,
        "maximum_compute_seconds": policy.maximum_compute_seconds,
        "maximum_task_duration_seconds": int(policy.maximum_task_duration.total_seconds()),
        "minimum_security_level": policy.security.minimum_security_level,
        "minimum_privacy_level": policy.security.minimum_privacy_level,
        "independent_verification_required": policy.verification.independent_verification_required,
        "evidence_required": policy.verification.evidence_required,
    }


def definition_of_done_record(definition: DefinitionOfDone) -> dict[str, object]:
    return {
        "definition_id": definition.definition_id,
        "work_order_id": definition.work_order_id,
        "deliverable_type": definition.deliverable_type,
        "requirements": list(definition.requirements),
        "acceptance_criteria": [
            {"criterion_id": item.criterion_id, "description": item.description, "required": item.required}
            for item in definition.acceptance_criteria
        ],
        "required_tests": list(definition.required_tests),
        "required_standards": list(definition.required_standards),
        "required_evidence": [
            {"evidence_type": item.evidence_type, "description": item.description}
            for item in definition.required_evidence
        ],
        "required_verification": list(definition.required_verification),
        "human_review_required": definition.human_review.required,
        "licensed_review_required": definition.human_review.licensed_reviewer_required,
        "minimum_quality": definition.minimum_quality,
        "completion_policy_version": definition.completion_policy_version,
    }


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


def verification_plan_record(plan: VerificationPlan) -> dict[str, object]:
    return {
        "work_order_id": plan.work_order_id,
        "assignments": [
            {
                "task_id": item.task_id,
                "builder_role_id": item.builder_role_id,
                "verifier_role_id": item.verifier_role_id,
                "verification_checks": list(item.verification_checks),
                "evidence_required": item.evidence_required,
                "human_review_required": item.human_review_required,
                "licensed_review_required": item.licensed_review_required,
                "independence_required": item.independence_required,
            }
            for item in plan.assignments
        ],
    }


def swarm_plan_record(plan: SwarmPlan) -> dict[str, object]:
    return {
        "plan_id": plan.plan_id,
        "work_order_id": plan.work_order_id,
        "employer_policy_id": plan.employer_policy_id,
        "task_order": list(plan.task_order),
        "assignments": [
            {
                "task_id": item.task_id,
                "role_id": item.role_id,
                "allowed_tools": list(item.allowed_tools),
                "allowed_data_scopes": list(item.allowed_data_scopes),
                "maximum_cost_cad": item.maximum_cost_cad,
                "maximum_tokens": item.maximum_tokens,
                "human_review_required": item.human_review_required,
                "execution_authorized": item.execution_authorized,
            }
            for item in plan.assignments
        ],
        "verification_plan_id": f"verification-{plan.work_order_id}",
        "compute_requirement_ids": [item.requirement_id for item in plan.compute_requirements],
        "maximum_cost_cad": plan.maximum_cost_cad,
        "maximum_tokens": plan.maximum_tokens,
        "execution_authorized": plan.execution_authorized,
    }
