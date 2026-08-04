from __future__ import annotations

import json
from pathlib import Path

import pytest

from scripts.run_exact_sha_ci_contract import EXPECTED_STAGES
from scripts.validate_exact_sha_ci_request import REQUIRED_CHECKS, validate_request


def valid_request() -> dict:
    return {
        "schema_version": "1.0.0",
        "request_id": "CI-RECEIPT-BA6110A-0001",
        "repository": "Lornt1666/AIGC",
        "target_branch": "main",
        "target_sha": "a" * 40,
        "broker_revision": "b" * 40,
        "requested_checks": sorted(REQUIRED_CHECKS),
        "production_activation_authorized": False,
        "external_action_authorized": False,
    }


def write(tmp_path: Path, value: dict) -> Path:
    path = tmp_path / "request.json"
    path.write_text(json.dumps(value), encoding="utf-8")
    return path


def test_request_accepts_only_closed_contract(tmp_path):
    assert validate_request(write(tmp_path, valid_request()), "b" * 40)["target_sha"] == "a" * 40


@pytest.mark.parametrize("field,value", [
    ("production_activation_authorized", True), ("external_action_authorized", True),
    ("repository", "other/repo"), ("target_branch", "feature"),
    ("target_sha", "main"), ("broker_revision", "main"),
])
def test_request_rejects_authority_and_target_drift(tmp_path, field, value):
    request = valid_request(); request[field] = value
    with pytest.raises(ValueError): validate_request(write(tmp_path, request), "b" * 40)


def test_request_rejects_broker_revision_mismatch(tmp_path):
    with pytest.raises(ValueError, match="broker revision"):
        validate_request(write(tmp_path, valid_request()), "c" * 40)


def test_request_rejects_arbitrary_fields(tmp_path):
    request = valid_request(); request["command"] = "curl example.invalid"
    with pytest.raises(ValueError, match="closed contract"):
        validate_request(write(tmp_path, request))


def test_shared_runner_is_the_single_canonical_ci_path():
    ordinary = Path(".github/workflows/aigc-ci.yml").read_text(encoding="utf-8")
    broker = Path(".github/workflows/exact-sha-ci-receipt.yml").read_text(encoding="utf-8")
    invocation = "scripts/run_exact_sha_ci_contract.py"
    contract = "config/exact_sha_ci_validation_contract.json"
    assert invocation in ordinary and invocation in broker
    assert contract in ordinary and contract in broker
    assert "python -m pytest" not in ordinary
    assert "src/aigc.py validate" not in ordinary


def test_contract_has_complete_exact_stage_set_and_no_authority():
    contract = json.loads(Path("config/exact_sha_ci_validation_contract.json").read_text())
    assert [stage["id"] for stage in contract["stages"]] == EXPECTED_STAGES
    assert set(EXPECTED_STAGES) == REQUIRED_CHECKS
    assert contract["external_action_authorized"] is False
    assert contract["production_activation_authorized"] is False


def test_workflow_is_default_branch_controlled_read_only_and_pinned():
    workflow = Path(".github/workflows/exact-sha-ci-receipt.yml").read_text(encoding="utf-8")
    assert "workflow_dispatch:" in workflow and "push:" not in workflow
    assert "github.workflow_sha" in workflow and "GITHUB_WORKFLOW_SHA" in workflow
    assert "$RUNNER_TEMP/exact-sha-stage-results" in workflow
    assert "$RUNNER_TEMP/exact-sha-upload" in workflow
    assert "--verify-inventory" in workflow
    assert "contents: read" in workflow and "persist-credentials: false" in workflow
    assert "id-token: write" not in workflow and "terraform apply" not in workflow and "gmail.send" not in workflow
    for marker in ("actions/checkout@", "actions/setup-python@", "actions/upload-artifact@", "hashicorp/setup-terraform@"):
        for line in (line.strip() for line in workflow.splitlines() if marker in line):
            revision = line.split("@", 1)[1]
            assert len(revision) == 40 and all(c in "0123456789abcdef" for c in revision)


def test_stage_records_are_atomic_and_fully_bound():
    source = Path("scripts/run_exact_sha_ci_contract.py").read_text(encoding="utf-8")
    for marker in ("os.replace", "os.fsync", "target_sha", "tested_tree_sha", "broker_revision", "run_number", "run_id", "ordered_command_digest", "command_outcomes"):
        assert marker in source


def test_receipt_is_honest_and_upload_inventory_is_terminal():
    source = Path("scripts/build_exact_sha_ci_receipt.py").read_text(encoding="utf-8")
    assert '"workflow_conclusion_at_receipt": "pending"' in source
    assert '"broker_validation_conclusion": "success"' in source
    assert "upload_inventory.json" in source
    assert "final upload inventory mismatch" in source
    assert "verify_inventory(args.output_root)" in source
