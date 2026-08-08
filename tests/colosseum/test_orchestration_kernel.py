from datetime import datetime, timedelta, timezone
from dataclasses import replace

import pytest

from src.colosseum.compute_exchange import ComputeAdmission, ComputeCandidate, ResourceType
from src.colosseum.domain import (
    CapabilityEvidence,
    CapabilityVerdict,
    ConfidentialityClass,
    WorkOrder,
)
from src.colosseum.orchestration import (
    AgentRoleDefinition,
    CapabilityMatch,
    CompletionCriterion,
    DefinitionOfDone,
    EvidenceRequirement,
    HumanQualificationEvidence,
    HumanReviewRequirement,
    ProfessionalCredentialEvidence,
    QualificationStatus,
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
    VaultDataScope,
    VerificationPolicy,
)


NOW = datetime(2026, 8, 7, tzinfo=timezone.utc)


def scopes() -> tuple[VaultDataScope, VaultDataScope]:
    return (
        VaultDataScope(
            "scope-source",
            "vault-1",
            "employer-1",
            ConfidentialityClass.CONFIDENTIAL,
            "source material",
        ),
        VaultDataScope(
            "scope-work",
            "vault-1",
            "employer-1",
            ConfidentialityClass.CONFIDENTIAL,
            "work products",
        ),
    )


def platform(**overrides) -> PlatformBaseline:
    values = dict(
        jurisdiction=JurisdictionPolicy(("CA-QC", "CA-ON"), ("US",), False),
        confidentiality=ConfidentialityPolicy(
            ConfidentialityClass.INTERNAL,
            external_training_use_allowed=False,
        ),
        tools=ToolPolicy(
            ("git", "pytest", "review-tool"),
            ("shell-root",),
            external_api_allowed=False,
            open_source_allowed=True,
        ),
        models=ModelPolicy(
            allowed_models=("model-safe", "model-review"),
            prohibited_models=("model-prohibited",),
            allowed_providers=("google", "openai"),
            prohibited_providers=("untrusted",),
        ),
        security=SecurityPolicy(3, 3),
        human_review=HumanReviewPolicy(True, True, True),
        verification=VerificationPolicy(True, True),
        retention=RetentionPolicy(180, True),
    )
    values.update(overrides)
    return PlatformBaseline(**values)


def employer_policy(**overrides) -> EmployerPolicy:
    values = dict(
        policy_id="policy-1",
        employer_id="employer-1",
        vault_id="vault-1",
        engagement_id="engagement-1",
        jurisdiction=JurisdictionPolicy(("CA-QC",), (), False),
        confidentiality=ConfidentialityPolicy(
            ConfidentialityClass.CONFIDENTIAL,
            external_training_use_allowed=True,
        ),
        tools=ToolPolicy(
            ("git", "pytest", "review-tool"),
            (),
            external_api_allowed=True,
            open_source_allowed=False,
        ),
        models=ModelPolicy(
            allowed_models=("model-safe",),
            prohibited_models=("employer-denied",),
            allowed_providers=("google",),
            prohibited_providers=("untrusted",),
        ),
        data=DataPolicy("vault-1", "employer-1", scopes()),
        retention=RetentionPolicy(90, False),
        human_review=HumanReviewPolicy(False, False, False),
        security=SecurityPolicy(1, 1),
        verification=VerificationPolicy(False, False),
        maximum_cost_cad=30.0,
        maximum_token_budget=3000,
        maximum_compute_seconds=3600,
        maximum_task_duration=timedelta(minutes=30),
    )
    values.update(overrides)
    return EmployerPolicy(**values)


def effective():
    return EmployerPolicyCompiler().compile(
        platform=platform(),
        employer=employer_policy(),
    )


def work_order() -> WorkOrder:
    return WorkOrder(
        "work-1",
        "engagement-1",
        "Build and test bounded software artifact",
        ("req-1",),
        ("tests-pass",),
        True,
    )


def definition(**overrides) -> DefinitionOfDone:
    values = dict(
        definition_id="dod-1",
        work_order_id="work-1",
        deliverable_type="software",
        requirements=("Implement req-1",),
        acceptance_criteria=(
            CompletionCriterion("tests-pass", "tests pass"),
        ),
        required_tests=("pytest",),
        required_standards=("secure-coding",),
        required_evidence=(
            EvidenceRequirement("test-receipt", "pytest receipt"),
        ),
        required_verification=("independent-review",),
        human_review=HumanReviewRequirement(False),
        minimum_quality=0.9,
        completion_policy_version="1",
        source_requirement_ids=("req-1",),
        source_acceptance_criterion_ids=("tests-pass",),
    )
    values.update(overrides)
    return DefinitionOfDone(**values)


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


def capability(
    skill: str,
    *,
    evidence_id: str | None = None,
    verdict: CapabilityVerdict = CapabilityVerdict.VERIFIED_CAPABLE,
    human_review: bool = False,
) -> CapabilityEvidence:
    return CapabilityEvidence(
        evidence_id or f"cap-{skill}",
        "software",
        skill,
        verdict,
        (f"bench-{skill}",),
        (f"deliverable-{skill}",),
        10,
        9,
        human_review,
        (f"evidence://{skill}",),
        NOW,
    )


def roles() -> tuple[AgentRoleDefinition, ...]:
    source, work = scopes()
    return (
        AgentRoleDefinition(
            "coder",
            ("coding",),
            ("git", "pytest"),
            (source,),
            10.0,
            1000,
            maximum_compute_seconds=1800,
        ),
        AgentRoleDefinition(
            "verifier",
            ("verification", "review"),
            ("review-tool",),
            (work,),
            5.0,
            500,
            maximum_compute_seconds=900,
        ),
    )


def evidence() -> tuple[CapabilityEvidence, ...]:
    return (
        capability("coding"),
        capability("verification"),
    )


def plan(**overrides):
    values = dict(
        work_order=work_order(),
        dag=TaskDAG("work-1", (task(),)),
        effective_policy=effective(),
        definitions_of_done=(definition(),),
        capability_evidence=evidence(),
        roles=roles(),
        as_of=NOW,
    )
    values.update(overrides)
    return SwarmScheduler().plan(**values)


def test_policy_compiler_preserves_all_strict_controls():
    compiled = effective()
    assert compiled.allowed_jurisdictions == ("CA-QC",)
    assert "US" in compiled.prohibited_jurisdictions
    assert compiled.cross_border_allowed is False
    assert compiled.allowed_providers == ("google",)
    assert "untrusted" in compiled.prohibited_providers
    assert compiled.allowed_models == ("model-safe",)
    assert {"model-prohibited", "employer-denied"}.issubset(
        compiled.prohibited_models
    )
    assert compiled.external_api_allowed is False
    assert compiled.open_source_allowed is False
    assert compiled.external_training_use_allowed is False
    assert compiled.retention_days == 90
    assert compiled.deletion_required_after_retention is True
    assert compiled.minimum_security_level == 3
    assert compiled.minimum_privacy_level == 3
    assert compiled.review_required_for_external_effects is True
    assert compiled.review_required_for_restricted_work is True
    assert compiled.licensed_review_required_when_legally_restricted is True
    assert compiled.independent_verification_required is True
    assert compiled.evidence_required is True


def test_cross_employer_scope_injection_is_rejected():
    injected = VaultDataScope(
        "injected",
        "vault-other",
        "employer-other",
        ConfidentialityClass.CONFIDENTIAL,
        "malicious cross-employer scope",
    )
    with pytest.raises(ValueError, match="not bound"):
        DataPolicy("vault-1", "employer-1", (injected,))


def test_role_scope_must_exactly_match_authorized_vault_scope():
    source, _ = scopes()
    malformed = replace(source, purpose="changed purpose")
    bad_roles = (
        replace(roles()[0], allowed_data_scopes=(malformed,)),
        roles()[1],
    )
    with pytest.raises(ValueError, match="no eligible agent role"):
        plan(roles=bad_roles)


def test_definition_of_done_must_cover_all_work_order_requirements():
    incomplete = definition(source_requirement_ids=("wrong",))
    with pytest.raises(ValueError, match="omits WorkOrder obligations"):
        plan(definitions_of_done=(incomplete,))


def test_definition_of_done_must_cover_all_acceptance_criteria():
    incomplete = definition(source_acceptance_criterion_ids=("wrong",))
    with pytest.raises(ValueError, match="omits WorkOrder obligations"):
        plan(definitions_of_done=(incomplete,))


def test_external_effect_forces_human_review():
    external = task(external_effect=True, idempotency_required=True)
    result = plan(dag=TaskDAG("work-1", (external,)))
    assert result.assignments[0].human_review_required is True
    assert result.verification_plan.assignments[0].human_review_required is True


def test_verifier_requires_capability_evidence():
    with pytest.raises(ValueError, match="verifier"):
        plan(capability_evidence=(capability("coding"),))


def test_builder_cannot_self_certify():
    with pytest.raises(ValueError, match="self-certify"):
        VerificationAssignment(
            task_id="task-1",
            builder_role_id="coder",
            verifier_role_id="coder",
            verifier_capability_matches=(
                CapabilityMatch(
                    "verification",
                    "cap-verification",
                    CapabilityVerdict.VERIFIED_CAPABLE,
                ),
            ),
            qualification_evidence_refs=(),
            verification_checks=("pytest",),
            evidence_required=True,
            human_review_required=False,
            licensed_review_required=False,
            maximum_cost_cad=1.0,
            maximum_tokens=100,
            maximum_compute_seconds=60,
            compute_requirement_id="compute-verify-task-1",
            independence_required=True,
        )


def test_scheduler_is_deterministic_and_does_not_authorize_execution():
    first = plan()
    second = plan()
    assert (
        first.scheduling_decisions[0].inputs_digest
        == second.scheduling_decisions[0].inputs_digest
    )
    assert first.assignments[0].execution_authorized is False
    assert first.execution_authorized is False


def test_material_input_change_changes_decision_digest():
    first = plan()
    changed_definition = definition(minimum_quality=0.95)
    second = plan(definitions_of_done=(changed_definition,))
    assert (
        first.scheduling_decisions[0].inputs_digest
        != second.scheduling_decisions[0].inputs_digest
    )


def test_build_and_verification_budgets_are_bounded():
    result = plan()
    total_cost = sum(item.maximum_cost_cad for item in result.assignments) + sum(
        item.maximum_cost_cad for item in result.verification_plan.assignments
    )
    total_tokens = sum(item.maximum_tokens for item in result.assignments) + sum(
        item.maximum_tokens for item in result.verification_plan.assignments
    )
    total_compute = sum(
        item.maximum_compute_seconds for item in result.assignments
    ) + sum(
        item.maximum_compute_seconds
        for item in result.verification_plan.assignments
    )
    assert total_cost <= result.maximum_cost_cad
    assert total_tokens <= result.maximum_tokens
    assert total_compute <= result.maximum_compute_seconds
    assert len(result.compute_requirements) == 2
    assert {item.stage.value for item in result.compute_requirements} == {
        "BUILD",
        "VERIFY",
    }


def test_compute_requirement_preserves_complete_policy():
    requirement = plan().compute_requirements[0]
    assert requirement.allowed_jurisdictions == ("CA-QC",)
    assert requirement.allowed_providers == ("google",)
    assert requirement.allowed_models == ("model-safe",)
    assert "model-prohibited" in requirement.prohibited_models
    assert "untrusted" in requirement.prohibited_providers
    assert requirement.external_api_allowed is False
    assert requirement.open_source_allowed is False
    assert requirement.cross_border_allowed is False
    assert requirement.external_training_use_allowed is False
    assert requirement.confidentiality_class == ConfidentialityClass.CONFIDENTIAL


def test_expired_task_deadline_is_rejected():
    expired = task(deadline=NOW)
    with pytest.raises(ValueError, match="deadline"):
        plan(dag=TaskDAG("work-1", (expired,)))


def test_legally_restricted_work_requires_valid_credential():
    source, work = scopes()
    restricted_roles = (
        AgentRoleDefinition(
            "licensed-builder",
            ("engineering-signoff",),
            ("git",),
            (source,),
            10,
            500,
            qualified_human=True,
            licensed_specialist=True,
            human_identity_ref="human-1",
            maximum_compute_seconds=600,
        ),
        AgentRoleDefinition(
            "licensed-verifier",
            ("verification",),
            ("review-tool",),
            (work,),
            5,
            500,
            qualified_human=True,
            licensed_specialist=True,
            human_identity_ref="human-2",
            maximum_compute_seconds=600,
        ),
    )
    restricted_task = task(required_capabilities=("engineering-signoff",))
    restricted_evidence = (
        capability(
            "engineering-signoff",
            verdict=CapabilityVerdict.LEGALLY_RESTRICTED,
        ),
        capability("verification"),
    )
    with pytest.raises(ValueError, match="no eligible agent role"):
        plan(
            dag=TaskDAG("work-1", (restricted_task,)),
            roles=restricted_roles,
            capability_evidence=restricted_evidence,
        )

    active_from = NOW - timedelta(days=1)
    active_until = NOW + timedelta(days=30)
    credentials = (
        ProfessionalCredentialEvidence(
            "cred-builder",
            "human-1",
            "engineering",
            "professional-engineer",
            "qualified-authority",
            "CA-QC",
            active_from,
            active_until,
            QualificationStatus.ACTIVE,
            ("evidence://cred-builder",),
            "a" * 64,
        ),
        ProfessionalCredentialEvidence(
            "cred-verifier",
            "human-2",
            "engineering",
            "professional-engineer",
            "qualified-authority",
            "CA-QC",
            active_from,
            active_until,
            QualificationStatus.ACTIVE,
            ("evidence://cred-verifier",),
            "b" * 64,
        ),
    )
    result = plan(
        dag=TaskDAG("work-1", (restricted_task,)),
        roles=restricted_roles,
        capability_evidence=restricted_evidence,
        professional_credentials=credentials,
    )
    assert result.verification_plan.assignments[0].licensed_review_required


def test_expired_credential_is_rejected():
    expired = ProfessionalCredentialEvidence(
        "cred-expired",
        "human-1",
        "engineering",
        "professional-engineer",
        "qualified-authority",
        "CA-QC",
        NOW - timedelta(days=30),
        NOW - timedelta(days=1),
        QualificationStatus.ACTIVE,
        ("evidence://expired",),
        "c" * 64,
    )
    assert not expired.is_valid(as_of=NOW, allowed_jurisdictions=("CA-QC",))


def test_task_dag_rejects_cycle_and_missing_dependency():
    t1 = task(task_id="task-1")
    t2 = task(task_id="task-2")
    with pytest.raises(ValueError, match="cycle"):
        TaskDAG(
            "work-1",
            (t1, t2),
            (
                TaskDependency("task-1", "task-2"),
                TaskDependency("task-2", "task-1"),
            ),
        )
    with pytest.raises(ValueError, match="unknown task"):
        TaskDAG(
            "work-1",
            (t1,),
            (TaskDependency("missing", "task-1"),),
        )


def test_critical_path_and_parallel_readiness():
    t1 = task(task_id="task-a", estimated_effort_minutes=5)
    t2 = task(task_id="task-b", estimated_effort_minutes=7)
    t3 = task(task_id="task-c", estimated_effort_minutes=3)
    dag = TaskDAG(
        "work-1",
        (t1, t2, t3),
        (
            TaskDependency("task-a", "task-c"),
            TaskDependency("task-b", "task-c"),
        ),
    )
    assert {item.task_id for item in dag.ready_tasks(())} == {
        "task-a",
        "task-b",
    }
    assert dag.critical_path_minutes() == 10


def test_human_qualification_requires_valid_evidence_digest():
    with pytest.raises(ValueError, match="SHA-256"):
        HumanQualificationEvidence(
            "qual-1",
            "human-1",
            "specialist",
            "issuer",
            "CA-QC",
            NOW,
            NOW + timedelta(days=1),
            QualificationStatus.ACTIVE,
            ("evidence://qual",),
            "not-a-digest",
        )


def compute_candidate(**overrides) -> ComputeCandidate:
    values = dict(
        candidate_id="candidate-safe",
        provider="google",
        resource_type=ResourceType.AI_MODEL,
        model_or_runtime="model-safe",
        region="northamerica-northeast1",
        jurisdiction="CA-QC",
        confidentiality_capability=ConfidentialityClass.CONFIDENTIAL,
        security_level=3,
        privacy_level=3,
        encryption="TLS+AEAD",
        estimated_cost_cad=1.0,
        estimated_latency_ms=1000,
        predicted_quality=0.95,
        predicted_reliability=0.95,
        availability=0.99,
        commercial_use_allowed=True,
        benchmark_evidence_refs=("benchmark://safe",),
        capabilities=("coding",),
        admission=ComputeAdmission.ADMISSIBLE,
        tool_ids=("git",),
        uses_external_api=False,
        uses_open_source=False,
        cross_border=False,
        uses_external_training=False,
        estimated_compute_seconds=60,
    )
    values.update(overrides)
    return ComputeCandidate(**values)


def test_compute_candidate_must_respect_model_and_tool_policy():
    requirement = plan().compute_requirements[0]
    assert compute_candidate().satisfies(requirement)
    assert not compute_candidate(model_or_runtime="model-prohibited").satisfies(
        requirement
    )
    assert not compute_candidate(tool_ids=("shell-root",)).satisfies(requirement)


def test_compute_candidate_must_respect_data_handling_permissions():
    requirement = plan().compute_requirements[0]
    assert not compute_candidate(uses_external_api=True).satisfies(requirement)
    assert not compute_candidate(uses_open_source=True).satisfies(requirement)
    assert not compute_candidate(cross_border=True).satisfies(requirement)
    assert not compute_candidate(uses_external_training=True).satisfies(
        requirement
    )


def test_compute_candidate_must_respect_compute_reservation():
    requirement = plan().compute_requirements[0]
    assert not compute_candidate(
        estimated_compute_seconds=requirement.maximum_compute_seconds + 1
    ).satisfies(requirement)
