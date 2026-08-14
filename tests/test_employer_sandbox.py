from __future__ import annotations

import copy
import json
from pathlib import Path

import pytest
from jsonschema import Draft202012Validator, ValidationError

from src.core.epistemic.canonicalization import canonical_sha256
from src.operations.employer_sandbox import run_employer_sandbox


ROOT = Path(__file__).resolve().parents[1]
SCHEMA = json.loads(
    (ROOT / "schemas/aigc_employer_sandbox_receipt.schema.json").read_text(encoding="utf-8")
)


def test_receipt_validates_and_hash_binds_every_material_field():
    receipt = run_employer_sandbox()
    Draft202012Validator(SCHEMA).validate(receipt)
    unsigned = dict(receipt)
    unsigned.pop("receipt_id")
    unsigned.pop("receipt_sha256")
    assert receipt["receipt_sha256"] == canonical_sha256(unsigned)


def test_receipt_is_deterministic():
    assert run_employer_sandbox() == run_employer_sandbox()


def test_adversarial_scenario_is_blocked_with_first_blocker():
    receipt = run_employer_sandbox(scenario="PROMPT_INJECTION")
    assert receipt["terminal_status"] == "BLOCKED"
    assert receipt["first_blocker"]
    assert receipt["external_actions_performed"] == 0
    assert receipt["provider_calls_performed"] == 0


def test_schema_rejects_fabricated_external_action():
    receipt = copy.deepcopy(run_employer_sandbox())
    receipt["external_actions_performed"] = 1
    with pytest.raises(ValidationError):
        Draft202012Validator(SCHEMA).validate(receipt)


def test_non_sandbox_mode_and_cross_pack_capability_fail_closed():
    with pytest.raises(ValueError, match="mode"):
        run_employer_sandbox(mode="live")  # type: ignore[arg-type]
    with pytest.raises(ValueError, match="does not belong"):
        run_employer_sandbox(
            pack_id="OCC-ADMINISTRATIVE_COORDINATOR",
            capability_id="CAP-DATA_QUALITY",
        )
