from __future__ import annotations

from hashlib import sha256
import json
from pathlib import Path

import pytest

from scripts.build_exact_sha_ci_receipt import canonical as receipt_canonical
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


def test_request_accepts_only_closed_canonical_contract(tmp_path):
    assert validate_request(write(tmp_path, valid_request()), "b" * 40)["target_sha"] == "a" * 40


@pytest.mark.parametrize("field,value", [
    ("production_activation_authorized", True),
    ("external_action_authorized", True),
    ("repository", "other/repo"),
    ("target_branch", "feature"),
    ("target_sha", "main"),
    ("broker_revision", "main"),
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


def test_request_requires_exact_check_set(tmp_path):
    request = valid_request(); request["requested_checks"] = ["tests"]
    with pytest.raises(ValueError, match="canonical checks"):
        validate_request(write(tmp_path, request))


def test_workflow_is_default_branch_controlled_read_only_and_pinned():
    workflow = Path(".github/workflows/exact-sha-ci-receipt.yml").read_text(encoding="utf-8")
    assert "workflow_dispatch:" in workflow
    assert "push:" not in workflow
    assert "github.workflow_sha" in workflow
    assert "GITHUB_WORKFLOW_SHA" in workflow
    assert "git show \"$REQUEST_COMMIT_SHA:$request_path\"" in workflow
    assert "contents: read" in workflow
    assert "persist-credentials: false" in workflow
    assert "id-token: write" not in workflow
    assert "terraform apply" not in workflow
    assert "gmail.send" not in workflow
    for marker in ("actions/checkout@", "actions/setup-python@", "actions/upload-artifact@", "hashicorp/setup-terraform@"):
        for line in (line.strip() for line in workflow.splitlines() if marker in line):
            revision = line.split("@", 1)[1]
            assert len(revision) == 40 and all(c in "0123456789abcdef" for c in revision)


def test_validation_contract_matches_complete_stage_set():
    contract = json.loads(Path("config/exact_sha_ci_validation_contract.json").read_text())
    assert [stage["id"] for stage in contract["stages"]] == EXPECTED_STAGES
    assert set(EXPECTED_STAGES) == REQUIRED_CHECKS
    assert contract["external_action_authorized"] is False
    assert contract["production_activation_authorized"] is False


def test_receipt_builder_validates_machine_results_not_hardcoded_source():
    source = Path("scripts/build_exact_sha_ci_receipt.py").read_text(encoding="utf-8")
    assert "load_stage_records" in source
    assert 'value.get("status") != "success"' in source
    assert 'value.get("exit_code") != 0' in source
    assert "completion_manifest.json" in source
    assert "receipt_file_sha256" in source
    assert "artifact_manifest_file_sha256" in source


def test_receipt_digest_covers_all_persisted_phase_one_fields():
    receipt = {"schema_version": "1.0.0", "request_sha256": "a" * 64, "requested_target_sha": "b" * 40,
        "observed_checkout_sha": "b" * 40, "tested_tree_sha": "c" * 40, "broker_revision": "d" * 40,
        "validation_contract_sha256": "e" * 64, "run_number": 1, "run_id": 2, "job_conclusion": "success",
        "step_conclusions": {name: "success" for name in EXPECTED_STAGES}, "test_result": "passed",
        "artifact_manifest_sha256": "f" * 64, "external_action_performed": False,
        "production_activation_authorized": False}
    digest = sha256(receipt_canonical(receipt)).hexdigest()
    receipt["receipt_sha256"] = digest
    persisted = dict(receipt); observed = persisted.pop("receipt_sha256")
    assert sha256(receipt_canonical(persisted)).hexdigest() == observed
