from dataclasses import replace
from datetime import timedelta

import pytest

from scripts.validate_governed_orchestration_bundle import (
    NOW,
    build_governed_fixture,
)
from src.colosseum.domain import CapabilityEvidence, CapabilityVerdict
from src.colosseum.governed_bundle import (
    GovernedOrchestrationBundle,
    RoleQualificationRequirement,
)
from src.colosseum.orchestration import (
    CapabilityMatch,
    HumanQualificationEvidence,
    ProfessionalCredentialEvidence,
    QualificationStatus,
    canonical_sha256,
)


def human_qualification(
    *,
    evidence_id: str = "qualification-1",
    identity: str = "human-1",
    qualification_class: str = "senior-reviewer",
) -> HumanQualificationEvidence:
    return HumanQualificationEvidence(
        qualification_evidence_id=evidence_id,
        human_identity_ref=identity,
        qualification_class=qualification_class,
        issuing_authority="synthetic-authority",
        jurisdiction="CA-QC",
        valid_from=NOW - timedelta(days=1),
        valid_until=NOW + timedelta(days=1),
        status=QualificationStatus.ACTIVE,
        evidence_refs=("evidence://qualification",),
        evidence_digest="a" * 64,
    )


def professional_credential(
    *,
    evidence_id: str = "credential-1",
    identity: str = "human-1",
    profession: str = "engineering",
    credential_class: str = "licensed-engineer",
) -> ProfessionalCredentialEvidence:
    return ProfessionalCredentialEvidence(
        credential_evidence_id=evidence_id,
        human_identity_ref=identity,
        profession=profession,
        credential_class=credential_class,
        issuing_authority="synthetic-regulator",
        jurisdiction="CA-QC",
        valid_from=NOW - timedelta(days=1),
        valid_until=NOW + timedelta(days=1),
        status=QualificationStatus.ACTIVE,
        evidence_refs=("evidence://credential",),
        evidence_digest="b" * 64,
    )


def replace_builder_capability(
    bundle: GovernedOrchestrationBundle,
    *,
    verdict: CapabilityVerdict,
    evidence_id: str,
    qualification_refs: tuple[str, ...],
) -> tuple:
    assignment = replace(
        bundle.swarm_plan.assignments[0],
        capability_matches=(CapabilityMatch("coding", evidence_id, verdict),),
        qualification_evidence_refs=qualification_refs,
    )
    decision = replace(
        bundle.swarm_plan.scheduling_decisions[0],
        capability_evidence_refs=(evidence_id,),
        qualification_evidence_refs=qualification_refs,
    )
    plan = replace(
        bundle.swarm_plan,
        assignments=(assignment,),
        scheduling_decisions=(decision,),
    )
    evidence = CapabilityEvidence(
        evidence_id,
        "software",
        "coding",
        verdict,
        ("benchmark-regulated",),
        ("deliverable-regulated",),
        1,
        1,
        True,
        ("evidence://regulated",),
        NOW,
    )
    verifier_evidence = next(
        item
        for item in bundle.capability_evidence
        if item.skill == "verification"
    )
    return plan, (evidence, verifier_evidence)


def test_governed_bundle_round_trip_and_authority_are_fail_closed() -> None:
    bundle = build_governed_fixture()
    record = bundle.to_record()
    assert GovernedOrchestrationBundle.from_record(record).to_record() == record

    tampered = dict(record)
    tampered["authority"] = dict(record["authority"])
    tampered["authority"]["merge_authorized"] = True
    unsigned = dict(tampered)
    unsigned.pop("record_sha256")
    tampered["record_sha256"] = canonical_sha256(unsigned)
    with pytest.raises(ValueError, match="prohibited authority"):
        GovernedOrchestrationBundle.from_record(tampered)


def test_dangling_capability_evidence_is_rejected() -> None:
    bundle = build_governed_fixture()
    assignment = replace(
        bundle.swarm_plan.assignments[0],
        capability_matches=(
            CapabilityMatch(
                "coding",
                "missing-evidence",
                CapabilityVerdict.VERIFIED_CAPABLE,
            ),
        ),
    )
    plan = replace(bundle.swarm_plan, assignments=(assignment,))
    with pytest.raises(ValueError, match="missing evidence"):
        replace(bundle, swarm_plan=plan)


def test_specialist_requires_matching_identity_and_qualification_class() -> None:
    bundle = build_governed_fixture()
    qualification = human_qualification()
    plan, evidence = replace_builder_capability(
        bundle,
        verdict=CapabilityVerdict.CAPABLE_WITH_SPECIALIST,
        evidence_id="cap-specialist",
        qualification_refs=(qualification.qualification_evidence_id,),
    )
    mismatched = RoleQualificationRequirement(
        role_id=plan.assignments[0].role_id,
        human_identity_ref="human-1",
        qualification_classes=("unrelated-class",),
    )
    with pytest.raises(ValueError, match="matching human qualification"):
        GovernedOrchestrationBundle(
            as_of=NOW,
            effective_policy=bundle.effective_policy,
            definitions_of_done=bundle.definitions_of_done,
            task_dag=bundle.task_dag,
            swarm_plan=plan,
            capability_evidence=evidence,
            human_qualifications=(qualification,),
            role_qualification_requirements=(mismatched,),
        )


def test_regulated_role_rejects_unrelated_professional_credential() -> None:
    bundle = build_governed_fixture()
    credential = professional_credential(profession="accounting")
    plan, evidence = replace_builder_capability(
        bundle,
        verdict=CapabilityVerdict.LEGALLY_RESTRICTED,
        evidence_id="cap-regulated",
        qualification_refs=(credential.credential_evidence_id,),
    )
    requirement = RoleQualificationRequirement(
        role_id=plan.assignments[0].role_id,
        human_identity_ref="human-1",
        professions=("engineering",),
        credential_classes=("licensed-engineer",),
    )
    with pytest.raises(ValueError, match="matching professional credential"):
        GovernedOrchestrationBundle(
            as_of=NOW,
            effective_policy=bundle.effective_policy,
            definitions_of_done=bundle.definitions_of_done,
            task_dag=bundle.task_dag,
            swarm_plan=plan,
            capability_evidence=evidence,
            professional_credentials=(credential,),
            role_qualification_requirements=(requirement,),
        )


def test_regulated_role_accepts_only_matching_active_credential_and_round_trips() -> None:
    bundle = build_governed_fixture()
    credential = professional_credential()
    plan, evidence = replace_builder_capability(
        bundle,
        verdict=CapabilityVerdict.LEGALLY_RESTRICTED,
        evidence_id="cap-regulated",
        qualification_refs=(credential.credential_evidence_id,),
    )
    requirement = RoleQualificationRequirement(
        role_id=plan.assignments[0].role_id,
        human_identity_ref="human-1",
        professions=("engineering",),
        credential_classes=("licensed-engineer",),
    )
    governed = GovernedOrchestrationBundle(
        as_of=NOW,
        effective_policy=bundle.effective_policy,
        definitions_of_done=bundle.definitions_of_done,
        task_dag=bundle.task_dag,
        swarm_plan=plan,
        capability_evidence=evidence,
        professional_credentials=(credential,),
        role_qualification_requirements=(requirement,),
    )
    record = governed.to_record()
    assert GovernedOrchestrationBundle.from_record(record).to_record() == record


def test_human_verifier_requires_role_bound_active_evidence() -> None:
    bundle = build_governed_fixture()
    qualification = human_qualification(
        identity="reviewer-human",
        qualification_class="independent-reviewer",
    )
    verification = replace(
        bundle.swarm_plan.verification_plan.assignments[0],
        human_review_required=True,
        qualification_evidence_refs=(qualification.qualification_evidence_id,),
    )
    plan = replace(
        bundle.swarm_plan,
        verification_plan=replace(
            bundle.swarm_plan.verification_plan,
            assignments=(verification,),
        ),
    )
    requirement = RoleQualificationRequirement(
        role_id=verification.verifier_role_id,
        human_identity_ref="reviewer-human",
        qualification_classes=("independent-reviewer",),
    )
    governed = GovernedOrchestrationBundle(
        as_of=NOW,
        effective_policy=bundle.effective_policy,
        definitions_of_done=bundle.definitions_of_done,
        task_dag=bundle.task_dag,
        swarm_plan=plan,
        capability_evidence=bundle.capability_evidence,
        human_qualifications=(qualification,),
        role_qualification_requirements=(requirement,),
    )
    assert governed.to_record()["authority"]["execution_authorized"] is False
