from __future__ import annotations

import json
from pathlib import Path

from jsonschema import Draft202012Validator


ROOT = Path(__file__).resolve().parents[2]
SCHEMA = ROOT / "schemas" / "identity_bound_work_acceptance.schema.json"


def validator() -> Draft202012Validator:
    schema = json.loads(SCHEMA.read_text(encoding="utf-8"))
    Draft202012Validator.check_schema(schema)
    return Draft202012Validator(schema)


def valid_command() -> dict[str, object]:
    return {
        "expected_revision": 2,
        "identity_receipt_id": "IDR-" + "A" * 24,
        "operator_role": "ACCOUNTABLE_OPERATOR",
        "reason": "Proceed with bounded internal work.",
    }


def test_identity_bound_command_accepts_minimum_safe_input() -> None:
    assert not list(validator().iter_errors(valid_command()))


def test_identity_bound_command_rejects_caller_authority_fields() -> None:
    value = valid_command()
    value["principal_id"] = "principal-attacker"
    value["roles"] = ["administrator"]
    value["assurance"] = {"ial": "IAL3"}

    assert list(validator().iter_errors(value))


def test_identity_bound_command_requires_pibc_receipt_shape() -> None:
    value = valid_command()
    value["identity_receipt_id"] = "temporary-receipt"

    assert list(validator().iter_errors(value))
