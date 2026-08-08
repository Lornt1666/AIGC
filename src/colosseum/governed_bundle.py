from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any, Iterable

from .domain import CapabilityEvidence, CapabilityVerdict, _require_text
from .orchestration import (
    DefinitionOfDone,
    HumanQualificationEvidence,
    ProfessionalCredentialEvidence,
    SwarmPlan,
    TaskDAG,
    canonical_sha256,
)
from .persistence import (
    definition_of_done_from_record,
    definition_of_done_record,
    effective_policy_from_record,
    effective_policy_record,
    human_qualification_from_record,
    human_qualification_record,
    professional_credential_from_record,
    professional_credential_record,
    swarm_plan_from_record,
    swarm_plan_record,
    task_dag_from_record,
    task_dag_record,
)
from .policy import EffectivePolicy


@dataclass(frozen=True)
class RoleQualificationRequirement:
    """Evidence classes accepted for one human-bound agent role."""

    role_id: str
    human_identity_ref: str
    qualification_classes: tuple[str, ...] = ()
    professions: tuple[str, ...] = ()
    credential_classes: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        _require_text("role_id", self.role_id)
        _require_text("human_identity_ref", self.human_identity_ref)
        for collection_name in (
            "qualification_classes",
            "professions",
            "credential_classes",
        ):
            values = getattr(self, collection_name)
            if len(values) != len(set(values)):
                raise ValueError(f"{collection_name} must be unique")
            for value in values:
                _require_text(collection_name, value)
        if bool(self.professions) != bool(self.credential_classes):
            raise ValueError(
                "professional role requirements need both profession and credential class"
            )
        if not self.qualification_classes and not self.professions:
            raise ValueError("role qualification requirement must constrain evidence")

    def accepts_qualification(self, evidence: HumanQualificationEvidence) -> bool:
        return (
            evidence.human_identity_ref == self.human_identity_ref
            and evidence.qualification_class in self.qualification_classes
        )

    def accepts_credential(self, evidence: ProfessionalCredentialEvidence) -> bool:
        return (
            evidence.human_identity_ref == self.human_identity_ref
            and evidence.profession in self.professions
            and evidence.credential_class in self.credential_classes
        )


@dataclass(frozen=True)
class GovernedOrchestrationBundle:
    """The mandatory pre-execution evidence and policy admission envelope."""

    as_of: datetime
    effective_policy: EffectivePolicy
    definitions_of_done: tuple[DefinitionOfDone, ...]
    task_dag: TaskDAG
    swarm_plan: SwarmPlan
    capability_evidence: tuple[CapabilityEvidence, ...]
    human_qualifications: tuple[HumanQualificationEvidence, ...] = ()
    professional_credentials: tuple[ProfessionalCredentialEvidence, ...] = ()
    role_qualification_requirements: tuple[
        RoleQualificationRequirement, ...
    ] = ()

    def __post_init__(self) -> None:
        if self.as_of.tzinfo is None:
            raise ValueError("bundle as_of must be timezone-aware")
        if not self.definitions_of_done:
            raise ValueError("bundle requires Definitions of Done")
        if not self.capability_evidence:
            raise ValueError("bundle requires capability evidence")
        if self.task_dag.work_order_id != self.swarm_plan.work_order_id:
            raise ValueError("bundle TaskDAG and SwarmPlan work orders differ")
        if self.swarm_plan.employer_policy_id != self.effective_policy.policy_id:
            raise ValueError("bundle SwarmPlan is bound to a different policy")

        definition_ids = [item.definition_id for item in self.definitions_of_done]
        if len(definition_ids) != len(set(definition_ids)):
            raise ValueError("DefinitionOfDone IDs must be unique")
        definitions = {item.definition_id: item for item in self.definitions_of_done}
        for task in self.task_dag.tasks:
            definition = definitions.get(task.definition_of_done_id)
            if definition is None:
                raise ValueError("task references missing DefinitionOfDone")
            if definition.work_order_id != self.task_dag.work_order_id:
                raise ValueError("DefinitionOfDone belongs to a different work order")

        capabilities = self._unique_map(
            self.capability_evidence,
            "capability_evidence_id",
        )
        human = self._unique_map(
            self.human_qualifications,
            "qualification_evidence_id",
        )
        credentials = self._unique_map(
            self.professional_credentials,
            "credential_evidence_id",
        )
        requirements = self._unique_map(
            self.role_qualification_requirements,
            "role_id",
        )
        qualification_ids = set(human) | set(credentials)
        if set(human) & set(credentials):
            raise ValueError("qualification and credential IDs must be globally unique")

        for assignment in self.swarm_plan.assignments:
            self._validate_capability_matches(
                assignment.capability_matches,
                capabilities,
            )
            self._require_known_refs(
                assignment.qualification_evidence_refs,
                qualification_ids,
            )
            verdicts = {match.verdict for match in assignment.capability_matches}
            if CapabilityVerdict.CAPABLE_WITH_SPECIALIST in verdicts:
                self._require_matching_human_qualification(
                    assignment.role_id,
                    assignment.qualification_evidence_refs,
                    requirements,
                    human,
                )
            if CapabilityVerdict.LEGALLY_RESTRICTED in verdicts:
                self._require_matching_professional_credential(
                    assignment.role_id,
                    assignment.qualification_evidence_refs,
                    requirements,
                    credentials,
                )

        for verification in self.swarm_plan.verification_plan.assignments:
            self._validate_capability_matches(
                verification.verifier_capability_matches,
                capabilities,
            )
            self._require_known_refs(
                verification.qualification_evidence_refs,
                qualification_ids,
            )
            if verification.licensed_review_required:
                self._require_matching_professional_credential(
                    verification.verifier_role_id,
                    verification.qualification_evidence_refs,
                    requirements,
                    credentials,
                )
            elif verification.human_review_required:
                self._require_matching_human_reviewer(
                    verification.verifier_role_id,
                    verification.qualification_evidence_refs,
                    requirements,
                    human,
                    credentials,
                )

        for decision in self.swarm_plan.scheduling_decisions:
            self._require_known_refs(
                decision.capability_evidence_refs,
                set(capabilities),
            )
            self._require_known_refs(
                decision.qualification_evidence_refs,
                qualification_ids,
            )
            if decision.qualification_evidence_refs:
                requirement = requirements.get(decision.selected_role)
                if requirement is None:
                    raise ValueError(
                        "scheduling decision qualification evidence lacks role binding"
                    )
                self._validate_all_role_refs(
                    requirement,
                    decision.qualification_evidence_refs,
                    human,
                    credentials,
                )

    @staticmethod
    def _unique_map(items: Iterable[object], attribute: str) -> dict[str, object]:
        result: dict[str, object] = {}
        for item in items:
            identifier = str(getattr(item, attribute))
            if identifier in result:
                raise ValueError(f"duplicate evidence identifier: {identifier}")
            result[identifier] = item
        return result

    @staticmethod
    def _require_known_refs(refs: tuple[str, ...], known: set[str]) -> None:
        unknown = set(refs) - known
        if unknown:
            raise ValueError("bundle contains dangling evidence references")

    @staticmethod
    def _validate_capability_matches(matches, evidence_by_id: dict[str, object]) -> None:
        for match in matches:
            evidence = evidence_by_id.get(match.evidence_id)
            if not isinstance(evidence, CapabilityEvidence):
                raise ValueError("capability match references missing evidence")
            if evidence.skill != match.capability or evidence.verdict != match.verdict:
                raise ValueError("capability match does not agree with source evidence")

    def _valid_human(
        self,
        evidence: HumanQualificationEvidence,
        requirement: RoleQualificationRequirement,
    ) -> bool:
        return (
            requirement.accepts_qualification(evidence)
            and evidence.is_valid(
                as_of=self.as_of,
                allowed_jurisdictions=self.effective_policy.allowed_jurisdictions,
            )
        )

    def _valid_credential(
        self,
        evidence: ProfessionalCredentialEvidence,
        requirement: RoleQualificationRequirement,
    ) -> bool:
        return (
            requirement.accepts_credential(evidence)
            and evidence.is_valid(
                as_of=self.as_of,
                allowed_jurisdictions=self.effective_policy.allowed_jurisdictions,
            )
        )

    def _require_matching_human_qualification(
        self,
        role_id: str,
        refs: tuple[str, ...],
        requirements: dict[str, object],
        human: dict[str, object],
    ) -> None:
        requirement = requirements.get(role_id)
        if not isinstance(requirement, RoleQualificationRequirement):
            raise ValueError("specialist assignment lacks role qualification policy")
        if not any(
            isinstance(human.get(ref), HumanQualificationEvidence)
            and self._valid_human(human[ref], requirement)
            for ref in refs
        ):
            raise ValueError("specialist assignment lacks matching human qualification")
        self._validate_all_role_refs(requirement, refs, human, {})

    def _require_matching_professional_credential(
        self,
        role_id: str,
        refs: tuple[str, ...],
        requirements: dict[str, object],
        credentials: dict[str, object],
    ) -> None:
        requirement = requirements.get(role_id)
        if not isinstance(requirement, RoleQualificationRequirement):
            raise ValueError("regulated assignment lacks role credential policy")
        if not any(
            isinstance(credentials.get(ref), ProfessionalCredentialEvidence)
            and self._valid_credential(credentials[ref], requirement)
            for ref in refs
        ):
            raise ValueError("regulated assignment lacks matching professional credential")
        self._validate_all_role_refs(requirement, refs, {}, credentials)

    def _require_matching_human_reviewer(
        self,
        role_id: str,
        refs: tuple[str, ...],
        requirements: dict[str, object],
        human: dict[str, object],
        credentials: dict[str, object],
    ) -> None:
        requirement = requirements.get(role_id)
        if not isinstance(requirement, RoleQualificationRequirement):
            raise ValueError("human review lacks role qualification policy")
        valid = any(
            isinstance(human.get(ref), HumanQualificationEvidence)
            and self._valid_human(human[ref], requirement)
            for ref in refs
        ) or any(
            isinstance(credentials.get(ref), ProfessionalCredentialEvidence)
            and self._valid_credential(credentials[ref], requirement)
            for ref in refs
        )
        if not valid:
            raise ValueError("human review lacks matching active evidence")
        self._validate_all_role_refs(requirement, refs, human, credentials)

    def _validate_all_role_refs(
        self,
        requirement: RoleQualificationRequirement,
        refs: tuple[str, ...],
        human: dict[str, object],
        credentials: dict[str, object],
    ) -> None:
        for ref in refs:
            item = human.get(ref)
            if isinstance(item, HumanQualificationEvidence):
                if not self._valid_human(item, requirement):
                    raise ValueError("qualification evidence violates role binding")
                continue
            credential = credentials.get(ref)
            if isinstance(credential, ProfessionalCredentialEvidence):
                if not self._valid_credential(credential, requirement):
                    raise ValueError("credential evidence violates role binding")

    def to_record(self) -> dict[str, object]:
        record: dict[str, object] = {
            "schema_version": "1.0.0",
            "as_of": self.as_of.isoformat(),
            "effective_policy": effective_policy_record(self.effective_policy),
            "definitions_of_done": [
                definition_of_done_record(item)
                for item in self.definitions_of_done
            ],
            "task_dag": task_dag_record(self.task_dag),
            "swarm_plan": swarm_plan_record(self.swarm_plan),
            "capability_evidence": [
                capability_evidence_record(item)
                for item in self.capability_evidence
            ],
            "human_qualifications": [
                human_qualification_record(item)
                for item in self.human_qualifications
            ],
            "professional_credentials": [
                professional_credential_record(item)
                for item in self.professional_credentials
            ],
            "role_qualification_requirements": [
                role_qualification_requirement_record(item)
                for item in self.role_qualification_requirements
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

    @classmethod
    def from_record(cls, record: dict[str, Any]) -> GovernedOrchestrationBundle:
        source = dict(record)
        expected_digest = source.pop("record_sha256", None)
        if not isinstance(expected_digest, str):
            raise ValueError("governed bundle requires a record digest")
        if canonical_sha256(source) != expected_digest:
            raise ValueError("governed bundle record digest mismatch")
        if source.get("schema_version") != "1.0.0":
            raise ValueError("unsupported governed bundle schema version")
        authority = source.get("authority")
        expected_authority = {
            "execution_authorized": False,
            "external_action_authorized": False,
            "merge_authorized": False,
            "deployment_authorized": False,
            "live_model_call_authorized": False,
            "financial_action_authorized": False,
        }
        if authority != expected_authority:
            raise ValueError("governed bundle grants prohibited authority")
        bundle = cls(
            as_of=datetime.fromisoformat(str(source["as_of"])),
            effective_policy=effective_policy_from_record(source["effective_policy"]),
            definitions_of_done=tuple(
                definition_of_done_from_record(item)
                for item in source["definitions_of_done"]
            ),
            task_dag=task_dag_from_record(source["task_dag"]),
            swarm_plan=swarm_plan_from_record(source["swarm_plan"]),
            capability_evidence=tuple(
                capability_evidence_from_record(item)
                for item in source["capability_evidence"]
            ),
            human_qualifications=tuple(
                human_qualification_from_record(item)
                for item in source["human_qualifications"]
            ),
            professional_credentials=tuple(
                professional_credential_from_record(item)
                for item in source["professional_credentials"]
            ),
            role_qualification_requirements=tuple(
                role_qualification_requirement_from_record(item)
                for item in source["role_qualification_requirements"]
            ),
        )
        if bundle.to_record() != record:
            raise ValueError("governed bundle round trip lost information")
        return bundle


def capability_evidence_record(evidence: CapabilityEvidence) -> dict[str, object]:
    return {
        "capability_evidence_id": evidence.capability_evidence_id,
        "discipline": evidence.discipline,
        "skill": evidence.skill,
        "verdict": evidence.verdict.value,
        "benchmark_ids": list(evidence.benchmark_ids),
        "accepted_deliverable_ids": list(evidence.accepted_deliverable_ids),
        "validated_attempts": evidence.validated_attempts,
        "successful_attempts": evidence.successful_attempts,
        "human_review_required": evidence.human_review_required,
        "evidence_refs": list(evidence.evidence_refs),
        "last_verified_at": evidence.last_verified_at.isoformat(),
    }


def capability_evidence_from_record(record: dict[str, Any]) -> CapabilityEvidence:
    return CapabilityEvidence(
        capability_evidence_id=str(record["capability_evidence_id"]),
        discipline=str(record["discipline"]),
        skill=str(record["skill"]),
        verdict=CapabilityVerdict(str(record["verdict"])),
        benchmark_ids=tuple(record["benchmark_ids"]),
        accepted_deliverable_ids=tuple(record["accepted_deliverable_ids"]),
        validated_attempts=int(record["validated_attempts"]),
        successful_attempts=int(record["successful_attempts"]),
        human_review_required=bool(record["human_review_required"]),
        evidence_refs=tuple(record["evidence_refs"]),
        last_verified_at=datetime.fromisoformat(str(record["last_verified_at"])),
    )


def role_qualification_requirement_record(
    requirement: RoleQualificationRequirement,
) -> dict[str, object]:
    return {
        "role_id": requirement.role_id,
        "human_identity_ref": requirement.human_identity_ref,
        "qualification_classes": list(requirement.qualification_classes),
        "professions": list(requirement.professions),
        "credential_classes": list(requirement.credential_classes),
    }


def role_qualification_requirement_from_record(
    record: dict[str, Any],
) -> RoleQualificationRequirement:
    return RoleQualificationRequirement(
        role_id=str(record["role_id"]),
        human_identity_ref=str(record["human_identity_ref"]),
        qualification_classes=tuple(record["qualification_classes"]),
        professions=tuple(record["professions"]),
        credential_classes=tuple(record["credential_classes"]),
    )
