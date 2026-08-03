from __future__ import annotations

from hashlib import sha256
import json
from pathlib import Path
import subprocess

import pytest

from scripts.build_exact_sha_ci_receipt import canonical as receipt_canonical
from scripts.validate_exact_sha_ci_request import REQUIRED_CHECKS, validate_request


def valid_request() -> dict:
    return {
        "schema_version": "1.0.0",
        "request_id": "CI-RECEIPT-BA6110A-0001",
        "repository": "Lornt1666/AIGC",
        "target_branch": "main",
        "target_sha": "a" * 40,
        "requested_checks": sorted(REQUIRED_CHECKS),
        "production_activation_authorized": False,
        "external_action_authorized": False,
    }


def write(tmp_path: Path, value: dict) -> Path:
    path = tmp_path / "request.json"
    path.write_text(json.dumps(value), encoding="utf-8")
    return path


def test_request_accepts_only_closed_canonical_contract(tmp_path):
    assert validate_request(write(tmp_path, valid_request()))["target_sha"] == "a" * 40


@pytest.mark.parametrize("field,value", [
    ("production_activation_authorized", True),
    ("external_action_authorized", True),
    ("repository", "other/repo"),
    ("target_branch", "feature"),
    ("target_sha", "main"),
])
def test_request_rejects_authority_and_target_drift(tmp_path, field, value):
    request = valid_request(); request[field] = value
    with pytest.raises(ValueError): validate_request(write(tmp_path, request))


def test_request_rejects_arbitrary_fields(tmp_path):
    request = valid_request(); request["command"] = "curl example.invalid"
    with pytest.raises(ValueError, match="closed contract"):
        validate_request(write(tmp_path, request))


def test_request_requires_exact_check_set(tmp_path):
    request = valid_request(); request["requested_checks"] = ["tests"]
    with pytest.raises(ValueError, match="canonical checks"):
        validate_request(write(tmp_path, request))


def test_workflow_is_read_only_pinned_and_has_no_provider_authority():
    workflow = Path(".github/workflows/exact-sha-ci-receipt.yml").read_text(encoding="utf-8")
    assert "contents: read" in workflow
    assert "persist-credentials: false" in workflow
    assert "id-token: write" not in workflow
    assert "terraform apply" not in workflow
    assert "gmail.send" not in workflow
    assert "workflow_dispatch" not in workflow
    for marker in ("actions/checkout@", "actions/setup-python@", "actions/upload-artifact@", "hashicorp/setup-terraform@"):
        for line in (line.strip() for line in workflow.splitlines() if marker in line):
            revision = line.split("@", 1)[1]
            assert len(revision) == 40 and all(c in "0123456789abcdef" for c in revision)


def test_receipt_digest_covers_all_persisted_fields_except_digest():
    receipt = {
        "schema_version": "1.0.0", "request_sha256": "a" * 64,
        "requested_target_sha": "b" * 40, "observed_checkout_sha": "b" * 40,
        "tested_tree_sha": "c" * 40, "workflow_revision": "d" * 40,
        "run_number": 1, "run_id": 2, "job_conclusion": "success",
        "step_conclusions": {name: "success" for name in REQUIRED_CHECKS},
        "test_result": "passed", "artifact_manifest_sha256": "e" * 64,
        "external_action_performed": False, "production_activation_authorized": False,
    }
    digest = sha256(receipt_canonical(receipt)).hexdigest()
    receipt["receipt_sha256"] = digest
    persisted = dict(receipt); observed = persisted.pop("receipt_sha256")
    assert sha256(receipt_canonical(persisted)).hexdigest() == observed


def test_target_verification_commands_are_non_mutating():
    source = Path("scripts/validate_exact_sha_ci_request.py").read_text(encoding="utf-8")
    assert "git cat-file" not in source  # argv form only, never shell text
    assert "subprocess.run([\"git\", \"cat-file\"" in source
    assert "subprocess.run([\"git\", \"merge-base\", \"--is-ancestor\"" in source
    for prohibited in ("push", "commit", "reset", "checkout -b", "apply"):
        assert f'\"{prohibited}\"' not in source
