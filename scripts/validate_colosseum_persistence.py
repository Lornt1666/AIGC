from __future__ import annotations

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

import argparse
from datetime import datetime, timedelta, timezone
import json
from jsonschema import Draft202012Validator, FormatChecker

from src.colosseum.domain import (
    CapabilityEvidence,
    CapabilityVerdict,
    ConfidentialityClass,
    WorkOrder,
)
from src.colosseum.orchestration import (
    AgentRoleDefinition,
    CompletionCriterion,
    DefinitionOfDone,
    EvidenceRequirement,
    HumanReviewRequirement,
    SwarmScheduler,
    Task,
    TaskDAG,
)
from src.colosseum.persistence import (
    definition_of_done_from_record,
    definition_of_done_record,
    effective_policy_from_record,
    effective_policy_record,
    employer_policy_from_record,
    employer_policy_record,
    orchestration_bundle_record,
    swarm_plan_from_record,
    swarm_plan_record,
    task_dag_from_record,
    task_dag_record,
    verification_plan_from_record,
    verification_plan_record,
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


def build_fixture():
    source_scope = VaultDataScope(
        "scope-source",
        "vault-validation",
        "employer-validation",
        ConfidentialityClass.CONFIDENTIAL,
        "synthetic source",
    )
    work_scope = VaultDataScope(
        "scope-work",
        "vault-validation",
        "employer-validation",
        ConfidentialityClass.CONFIDENTIAL,
        "synthetic work",
    )
    platform = PlatformBaseline(
        jurisdiction=JurisdictionPolicy(("CA-QC",), ("US",), False),
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
            allowed_models=("synthetic-model",),
            prohibited_models=("prohibited-model",),
            allowed_providers=("synthetic-provider",),
            prohibited_providers=("untrusted",),
        ),
        security=SecurityPolicy(3, 3),
        human_review=HumanReviewPolicy(True, True, True),
        verification=VerificationPolicy(True, True),
        retention=RetentionPolicy(180, True),
    )
    employer = EmployerPolicy(
        policy_id="policy-validation",
        employer_id="employer-validation",
        vault_id="vault-validation",
        engagement_id="engagement-validation",
        jurisdiction=JurisdictionPolicy(("CA-QC",), (), False),
        confidentiality=ConfidentialityPolicy(
            ConfidentialityClass.CONFIDENTIAL,
            external_training_use_allowed=False,
        ),
        tools=ToolPolicy(
            ("git", "pytest", "review-tool"),
            (),
            external_api_allowed=False,
            open_source_allowed=False,
        ),
        models=ModelPolicy(
            allowed_models=("synthetic-model",),
            prohibited_models=(),
            allowed_providers=("synthetic-provider",),
            prohibited_providers=(),
        ),
        data=DataPolicy(
            "vault-validation",
            "employer-validation",
            (source_scope, work_scope),
        ),
        retention=RetentionPolicy(90, True),
        human_review=HumanReviewPolicy(True, True, True),
        security=SecurityPolicy(3, 3),
        verification=VerificationPolicy(True, True),
        maximum_cost_cad=10.0,
        maximum_token_budget=1000,
        maximum_compute_seconds=600,
        maximum_task_duration=timedelta(minutes=10),
    )
    effective = EmployerPolicyCompiler().compile(
        platform=platform,
        employer=employer,
    )
    work_order = WorkOrder(
        "work-validation",
        "engagement-validation",
        "Produce a synthetic validated artifact",
        ("requirement-validation",),
        ("acceptance-validation",),
        True,
    )
    definition = DefinitionOfDone(
        definition_id="dod-validation",
        work_order_id=work_order.work_order_id,
        deliverable_type="synthetic",
        requirements=("Produce synthetic output",),
        acceptance_criteria=(
            CompletionCriterion(
                "acceptance-validation",
                "Synthetic acceptance criterion passes",
            ),
        ),
        required_tests=("pytest",),
        required_standards=("synthetic-standard",),
        required_evidence=(
            EvidenceRequirement(
                "synthetic-receipt",
                "Deterministic synthetic receipt",
            ),
        ),
        required_verification=("independent-review",),
        human_review=HumanReviewRequirement(False),
        minimum_quality=0.9,
        completion_policy_version="1.0.0",
        source_requirement_ids=("requirement-validation",),
        source_acceptance_criterion_ids=("acceptance-validation",),
    )
    task = Task(
        task_id="task-validation",
        work_order_id=work_order.work_order_id,
        objective="Build synthetic artifact",
        task_type="synthetic",
        required_capabilities=("coding",),
        input_artifact_ids=(),
        expected_output_types=("synthetic-artifact",),
        definition_of_done_id=definition.definition_id,
        estimated_effort_minutes=5,
        parallelizable=False,
        external_effect=False,
        idempotency_required=False,
        human_review_required=False,
        deadline=NOW + timedelta(hours=1),
    )
    dag = TaskDAG(work_order.work_order_id, (task,))
    capability_evidence = (
        CapabilityEvidence(
            "cap-coding",
            "software",
            "coding",
            CapabilityVerdict.VERIFIED_CAPABLE,
            ("benchmark-coding",),
            ("deliverable-coding",),
            2,
            2,
            False,
            ("evidence://coding",),
            NOW,
        ),
        CapabilityEvidence(
            "cap-verification",
            "quality",
            "verification",
            CapabilityVerdict.VERIFIED_CAPABLE,
            ("benchmark-verification",),
            ("deliverable-verification",),
            2,
            2,
            False,
            ("evidence://verification",),
            NOW,
        ),
    )
    roles = (
        AgentRoleDefinition(
            "builder-validation",
            ("coding",),
            ("git", "pytest"),
            (source_scope,),
            4.0,
            400,
            maximum_compute_seconds=300,
        ),
        AgentRoleDefinition(
            "verifier-validation",
            ("verification",),
            ("review-tool",),
            (work_scope,),
            2.0,
            200,
            maximum_compute_seconds=150,
        ),
    )
    plan = SwarmScheduler().plan(
        work_order=work_order,
        dag=dag,
        effective_policy=effective,
        definitions_of_done=(definition,),
        capability_evidence=capability_evidence,
        roles=roles,
        as_of=NOW,
    )
    return effective, definition, dag, plan


def load_schema(root: Path, relative_path: str) -> dict:
    return json.loads((root / relative_path).read_text(encoding="utf-8"))


def validate(root: Path, relative_path: str, record: dict) -> None:
    Draft202012Validator(
        load_schema(root, relative_path),
        format_checker=FormatChecker(),
    ).validate(record)


def run_schema_validation(root: Path) -> dict[str, str]:
    effective, definition, dag, plan = build_fixture()
    records = {
        "employer_policy": (
            "schemas/employers/employer_policy.schema.json",
            employer_policy_record(effective.employer_policy),
        ),
        "effective_policy": (
            "schemas/employers/effective_policy.schema.json",
            effective_policy_record(effective),
        ),
        "definition_of_done": (
            "schemas/engagement/definition_of_done.schema.json",
            definition_of_done_record(definition),
        ),
        "task_dag": (
            "schemas/colosseum/task_dag.schema.json",
            task_dag_record(dag),
        ),
        "verification_plan": (
            "schemas/verification/verification_plan.schema.json",
            verification_plan_record(plan.verification_plan),
        ),
        "swarm_plan": (
            "schemas/colosseum/swarm_plan.schema.json",
            swarm_plan_record(plan),
        ),
        "qualification_evidence": (
            "schemas/verification/qualification_evidence.schema.json",
            {
                "human_qualifications": [],
                "professional_credentials": [],
            },
        ),
        "orchestration_bundle": (
            "schemas/colosseum/orchestration_bundle.schema.json",
            orchestration_bundle_record(
                effective_policy=effective,
                definitions_of_done=(definition,),
                task_dag=dag,
                swarm_plan=plan,
            ),
        ),
    }
    for name, (schema_path, record) in records.items():
        validate(root, schema_path, record)
    return {name: "PASS" for name in records}


def run_round_trip_validation() -> dict[str, str]:
    effective, definition, dag, plan = build_fixture()
    pairs = {
        "employer_policy": (
            employer_policy_record(effective.employer_policy),
            employer_policy_from_record,
            employer_policy_record,
        ),
        "effective_policy": (
            effective_policy_record(effective),
            effective_policy_from_record,
            effective_policy_record,
        ),
        "definition_of_done": (
            definition_of_done_record(definition),
            definition_of_done_from_record,
            definition_of_done_record,
        ),
        "task_dag": (
            task_dag_record(dag),
            task_dag_from_record,
            task_dag_record,
        ),
        "verification_plan": (
            verification_plan_record(plan.verification_plan),
            verification_plan_from_record,
            verification_plan_record,
        ),
        "swarm_plan": (
            swarm_plan_record(plan),
            swarm_plan_from_record,
            swarm_plan_record,
        ),
    }
    for name, (record, loader, dumper) in pairs.items():
        if dumper(loader(record)) != record:
            raise SystemExit(f"round trip lost information: {name}")
    return {name: "PASS" for name in pairs}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--mode",
        choices=("schema", "roundtrip", "all"),
        default="all",
    )
    parser.add_argument("--project-root", type=Path, default=Path("."))
    args = parser.parse_args()
    result: dict[str, object] = {
        "schema_version": "1.0.0",
        "mode": args.mode,
        "external_action_performed": False,
        "production_activation_authorized": False,
    }
    if args.mode in {"schema", "all"}:
        result["schema_validation"] = run_schema_validation(args.project_root)
    if args.mode in {"roundtrip", "all"}:
        result["round_trip_validation"] = run_round_trip_validation()
    print(json.dumps(result, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
