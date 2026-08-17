import json
from pathlib import Path

import pytest
from jsonschema import Draft202012Validator, FormatChecker

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
from tests.colosseum.test_orchestration_kernel import (
    definition,
    effective,
    plan,
    task,
)
from src.colosseum.orchestration import TaskDAG


ROOT = Path(__file__).resolve().parents[2]


def validate(schema_path: str, record: dict) -> None:
    schema = json.loads((ROOT / schema_path).read_text(encoding="utf-8"))
    Draft202012Validator(
        schema,
        format_checker=FormatChecker(),
    ).validate(record)


def test_employer_policy_round_trip_and_schema():
    source = effective().employer_policy
    record = employer_policy_record(source)
    validate("schemas/employers/employer_policy.schema.json", record)
    assert employer_policy_record(employer_policy_from_record(record)) == record


def test_effective_policy_round_trip_and_schema():
    source = effective()
    record = effective_policy_record(source)
    validate("schemas/employers/effective_policy.schema.json", record)
    assert effective_policy_record(effective_policy_from_record(record)) == record


def test_definition_of_done_round_trip_and_schema():
    source = definition()
    record = definition_of_done_record(source)
    validate("schemas/engagement/definition_of_done.schema.json", record)
    assert definition_of_done_record(definition_of_done_from_record(record)) == record


def test_task_dag_round_trip_and_schema():
    source = TaskDAG("work-1", (task(),))
    record = task_dag_record(source)
    validate("schemas/colosseum/task_dag.schema.json", record)
    assert task_dag_record(task_dag_from_record(record)) == record


def test_verification_plan_round_trip_and_schema():
    source = plan().verification_plan
    record = verification_plan_record(source)
    validate("schemas/verification/verification_plan.schema.json", record)
    assert verification_plan_record(verification_plan_from_record(record)) == record


def test_swarm_plan_round_trip_and_schema():
    source = plan()
    record = swarm_plan_record(source)
    validate("schemas/colosseum/swarm_plan.schema.json", record)
    reconstructed = swarm_plan_from_record(record)
    assert swarm_plan_record(reconstructed) == record


def test_swarm_plan_digest_detects_tampering():
    record = swarm_plan_record(plan())
    record["maximum_tokens"] = int(record["maximum_tokens"]) + 1
    with pytest.raises(ValueError, match="digest mismatch"):
        swarm_plan_from_record(record)


def test_orchestration_bundle_authority_is_fail_closed():
    result = plan()
    bundle = orchestration_bundle_record(
        effective_policy=effective(),
        definitions_of_done=(definition(),),
        task_dag=TaskDAG("work-1", (task(),)),
        swarm_plan=result,
    )
    validate("schemas/colosseum/orchestration_bundle.schema.json", bundle)
    assert all(value is False for value in bundle["authority"].values())


def test_schema_rejects_execution_authority_escalation():
    record = swarm_plan_record(plan())
    record["execution_authorized"] = True
    schema = json.loads(
        (ROOT / "schemas/colosseum/swarm_plan.schema.json").read_text(
            encoding="utf-8"
        )
    )
    errors = list(Draft202012Validator(schema).iter_errors(record))
    assert errors
