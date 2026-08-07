from datetime import datetime, timedelta, timezone

import pytest

from src.colosseum.domain import CapabilityEvidence, CapabilityVerdict, ConfidentialityClass, WorkOrder
from src.colosseum.orchestration import (
    AgentRoleDefinition,
    CompletionCriterion,
    DefinitionOfDone,
    EvidenceRequirement,
    HumanReviewRequirement,
    SwarmScheduler,
    Task,
    TaskDAG,
    TaskDependency,
    VerificationAssignment,
)
from src.colosseum.policy import (
    ConfidentialityPolicy,
    DataPolicy,
    EmployerPolicy,
    EmployerPolicyCompiler,
    HumanReviewPolicy,
    JurisdictionPolicy,
    ModelPolicy,
    PlatformBaseline,
    RetentionPolicy,
    SecurityPolicy,
    ToolPolicy,
    VerificationPolicy,
)


NOW = datetime(2026, 8, 7, tzinfo=timezone.utc)


def platform() -> PlatformBaseline:
    return PlatformBaseline(
        jurisdiction=JurisdictionPolicy(("CA-QC", "CA-ON"), ("US",)),
        confidentiality=ConfidentialityPolicy(ConfidentialityClass.INTERNAL),
        tools=ToolPolicy(("git", "pytest", "review-tool"), ("shell-root",)),
        models=ModelPolicy(allowed_providers=("google", "openai"), prohibited_providers=("untrusted",)),
        security=SecurityPolicy(3, 3),
        human_review=HumanReviewPolicy(),
        verification=VerificationPolicy(True, True),
    )


def employer_policy(**overrides) -> EmployerPolicy:
    values = dict(
        policy_id="policy-1",
        employer_id="employer-1",
        vault_id="vault-1",
        engagement_id="engagement-1",
        jurisdiction=JurisdictionPolicy(("CA-QC",)),
        confidentiality=ConfidentialityPolicy(ConfidentialityClass.CONFIDENTIAL),
        tools=ToolPolicy(("git", "pytest", "review-tool"), ()),
        models=ModelPolicy(allowed_providers=("google",), prohibited_providers=("untrusted",)),
        data=DataPolicy("vault-1", ("employer-1:source", "employer-1:work")),
        retention=RetentionPolicy(90),
        human_review=HumanReviewPolicy(),
        security=SecurityPolicy(1, 1),
        verification=VerificationPolicy(True, True),
        maximum_cost_cad=30.0,
        maximum_token_budget=3000,
        maximum_compute_seconds=3600,
        maximum_task_duration=timedelta(minutes=30),
    )
    values.update(overrides)
    return EmployerPolicy(**values)


def work_order() -> WorkOrder:
    return WorkOrder("work-1", "engagement-1", "Build and test bounded software artifact", ("req-1",), ("tests-pass",), True)


def definition() -> DefinitionOfDone:
    return DefinitionOfDone(
        definition_id="dod-1",
        work_order_id="work-1",
        deliverable_type="software",
        requirements=("req-1",),
        acceptance_criteria=(CompletionCriterion("criterion-1", "tests pass"),),
        required_tests=("pytest",),
        required_standards=("secure-coding",),
        required_evidence=(EvidenceRequirement("test-receipt", "pytest receipt"),),
        required_verification=("independent-review",),
        human_review=HumanReviewRequirement(False),
        minimum_quality=0.9,
        completion_policy_version="1",
    )


def task(**overrides) -> Task:
    values = dict(
        task_id="task-1",
        work_order_id="work-1",
        objective="Implement bounded change",
        task_type="software",
        required_capabilities=("coding",),
        input_artifact_ids=(),
        expected_output_types=("source-code",),
        definition_of_done_id="dod-1",
        estimated_effort_minutes=10,
        parallelizable=True,
        external_effect=False,
        idempotency_required=False,
        human_review_required=False,
        deadline=NOW + timedelta(hours=1),
        priority=1,
    )
    values.update(overrides)
    return Task(**values)


def evidence(verdict=CapabilityVerdict.VERIFIED_CAPABLE, human_review=False) -> CapabilityEvidence:
    return CapabilityEvidence(
        "cap-1", "software", "coding", verdict, ("bench-1",), ("deliverable-1",), 10, 9,
        human_review, ("evidence://cap-1",), NOW,
    )


def roles() -> tuple[AgentRoleDefinition, ...]:
    return (
        AgentRoleDefinition("coder", ("coding",), ("git", "pytest"), ("employer-1:source",), 10.0, 1000),
        AgentRoleDefinition("verifier", ("verification", "review"), ("review-tool",), ("employer-1:work",), 5.0, 500),
    )


def effective():
    return EmployerPolicyCompiler().compile(platform=platform(), employer=employer_policy())


def test_employer_policy_cannot_weaken_platform_security():
    compiled = effective()
    assert compiled.minimum_security_level == 3
    assert compiled.minimum_privacy_level == 3
    assert compiled.minimum_confidentiality_class == ConfidentialityClass.CONFIDENTIAL


def test_platform_provider_deny_survives_compilation():
    compiled = effective()
    assert "untrusted" in compiled.prohibited_providers


def test_cross_employer_data_scope_cannot_be_scheduled():
    bad_roles = (
        AgentRoleDefinition("coder", ("coding",), ("git",), ("employer-2:source",), 10.0, 1000),
        roles()[1],
    )
    with pytest.raises(ValueError, match="no eligible agent role"):
        SwarmScheduler().plan(
            work_order=work_order(), dag=TaskDAG("work-1", (task(),)), effective_policy=effective(),
            definitions_of_done=(definition(),), capability_evidence=(evidence(),), roles=bad_roles,
        )


def test_not_qualified_capability_cannot_be_assigned():
    with pytest.raises(ValueError, match="no eligible agent role"):
        SwarmScheduler().plan(
            work_order=work_order(), dag=TaskDAG("work-1", (task(),)), effective_policy=effective(),
            definitions_of_done=(definition(),), capability_evidence=(evidence(CapabilityVerdict.NOT_QUALIFIED),), roles=roles(),
        )


def test_capable_with_review_marks_assignment_for_review():
    plan = SwarmScheduler().plan(
        work_order=work_order(), dag=TaskDAG("work-1", (task(),)), effective_policy=effective(),
        definitions_of_done=(definition(),), capability_evidence=(evidence(CapabilityVerdict.CAPABLE_WITH_REVIEW),), roles=roles(),
    )
    assert plan.assignments[0].human_review_required is True


def test_external_effect_requires_idempotency():
    with pytest.raises(ValueError, match="requires idempotency"):
        task(external_effect=True, idempotency_required=False)


def test_task_dag_rejects_cycle():
    t1 = task(task_id="task-1")
    t2 = task(task_id="task-2")
    with pytest.raises(ValueError, match="cycle"):
        TaskDAG("work-1", (t1, t2), (TaskDependency("task-1", "task-2"), TaskDependency("task-2", "task-1")))


def test_task_dag_rejects_missing_dependency():
    with pytest.raises(ValueError, match="unknown task"):
        TaskDAG("work-1", (task(),), (TaskDependency("missing", "task-1"),))


def test_critical_path_and_parallel_readiness():
    t1 = task(task_id="task-a", estimated_effort_minutes=5)
    t2 = task(task_id="task-b", estimated_effort_minutes=7)
    t3 = task(task_id="task-c", estimated_effort_minutes=3)
    dag = TaskDAG("work-1", (t1, t2, t3), (TaskDependency("task-a", "task-c"), TaskDependency("task-b", "task-c")))
    assert {item.task_id for item in dag.ready_tasks(())} == {"task-a", "task-b"}
    assert dag.critical_path_minutes() == 10


def test_builder_cannot_self_certify():
    with pytest.raises(ValueError, match="self-certify"):
        VerificationAssignment("task-1", "coder", "coder", ("test",), True, False, False, True)


def test_scheduler_is_deterministic_and_does_not_authorize_execution():
    kwargs = dict(
        work_order=work_order(), dag=TaskDAG("work-1", (task(),)), effective_policy=effective(),
        definitions_of_done=(definition(),), capability_evidence=(evidence(),), roles=roles(),
    )
    first = SwarmScheduler().plan(**kwargs)
    second = SwarmScheduler().plan(**kwargs)
    assert first.scheduling_decisions[0].inputs_digest == second.scheduling_decisions[0].inputs_digest
    assert first.assignments[0].execution_authorized is False
    assert first.execution_authorized is False


def test_compute_requirement_preserves_policy_and_scheduler_does_not_select_route():
    plan = SwarmScheduler().plan(
        work_order=work_order(), dag=TaskDAG("work-1", (task(),)), effective_policy=effective(),
        definitions_of_done=(definition(),), capability_evidence=(evidence(),), roles=roles(),
    )
    requirement = plan.compute_requirements[0]
    assert requirement.allowed_jurisdictions == ("CA-QC",)
    assert requirement.allowed_providers == ("google",)
    assert "untrusted" in requirement.prohibited_providers
    assert requirement.confidentiality_class == ConfidentialityClass.CONFIDENTIAL
    assert not hasattr(plan, "candidate_ids")


def test_assignment_budgets_are_subordinate_to_plan_budget():
    t1 = task(task_id="task-a")
    t2 = task(task_id="task-b")
    plan = SwarmScheduler().plan(
        work_order=work_order(), dag=TaskDAG("work-1", (t1, t2)), effective_policy=effective(),
        definitions_of_done=(definition(),), capability_evidence=(evidence(),), roles=roles(),
    )
    assert sum(item.maximum_cost_cad for item in plan.assignments) <= plan.maximum_cost_cad
    assert sum(item.maximum_tokens for item in plan.assignments) <= plan.maximum_tokens
