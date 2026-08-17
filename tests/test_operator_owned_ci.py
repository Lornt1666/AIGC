from __future__ import annotations

from datetime import datetime, timedelta, timezone
import importlib.metadata
import json
from pathlib import Path

import pytest
from jsonschema import Draft202012Validator, FormatChecker

from scripts.run_operator_owned_ci import (
    RunnerBlocked,
    check_exact_dependencies,
    claim_request,
    digest,
    execute_contract,
    load_contract,
    sanitized_environment,
    validate_request,
)


ROOT = Path(__file__).resolve().parents[1]
CONTRACT_PATH = ROOT / "config/aigc_operator_runner_contract.v1.json"
FULL_SHA = "a" * 40
TREE_SHA = "b" * 40
BASE_SHA = "c" * 40


def request_for(contract: dict, now: datetime) -> dict:
    return {
        "schema_version": "1.0.0",
        "request_id": "FORGE-20260817T000000Z-AAAAAAAAAAAA",
        "repository": "Lornt1666/AIGC",
        "target_sha": FULL_SHA,
        "expected_tree_sha": TREE_SHA,
        "trusted_base_sha": BASE_SHA,
        "broker_revision": FULL_SHA,
        "contract_path": "config/aigc_operator_runner_contract.v1.json",
        "contract_sha256": digest(contract),
        "requested_stages": [stage["id"] for stage in contract["stages"]],
        "approved_by": "RegenExcalibur / 1JGM",
        "approved_at": now.isoformat().replace("+00:00", "Z"),
        "expires_at": (now + timedelta(minutes=30)).isoformat().replace(
            "+00:00", "Z"
        ),
        "human_execution_approved": True,
        "network_policy": "process_environment_guard",
        "external_action_authorized": False,
        "production_activation_authorized": False,
        "provider_call_authorized": False,
        "secret_access_authorized": False,
    }


def test_canonical_contract_is_closed_and_inert():
    contract = load_contract(CONTRACT_PATH)
    assert contract["contract_id"] == "REGENEXCALIBUR-AIGC-FORGERUNNER-V1"
    assert contract["external_action_authorized"] is False
    assert contract["provider_call_authorized"] is False
    assert [stage["id"] for stage in contract["stages"]] == [
        "dependency_integrity",
        "python_compilation",
        "deterministic_evidence",
        "release_secret_scan",
        "tests",
    ]


def test_request_accepts_exact_time_bound_inert_authority():
    now = datetime.now(timezone.utc)
    contract = load_contract(CONTRACT_PATH)
    validate_request(request_for(contract, now), contract, now=now)


def test_request_schema_accepts_canonical_request():
    now = datetime.now(timezone.utc)
    contract = load_contract(CONTRACT_PATH)
    schema = json.loads(
        (ROOT / "schemas/aigc_operator_runner_request.schema.json").read_text(
            encoding="utf-8"
        )
    )
    Draft202012Validator.check_schema(schema)
    Draft202012Validator(schema, format_checker=FormatChecker()).validate(
        request_for(contract, now)
    )


@pytest.mark.parametrize(
    "field,value",
    [
        ("external_action_authorized", True),
        ("production_activation_authorized", True),
        ("provider_call_authorized", True),
        ("secret_access_authorized", True),
        ("human_execution_approved", False),
    ],
)
def test_request_rejects_authority_expansion(field: str, value: bool):
    now = datetime.now(timezone.utc)
    contract = load_contract(CONTRACT_PATH)
    request = request_for(contract, now)
    request[field] = value
    with pytest.raises(RunnerBlocked):
        validate_request(request, contract, now=now)


def test_request_rejects_expiry_and_tree_shape():
    now = datetime.now(timezone.utc)
    contract = load_contract(CONTRACT_PATH)
    expired = request_for(contract, now - timedelta(hours=1))
    with pytest.raises(RunnerBlocked, match="not currently valid"):
        validate_request(expired, contract, now=now)
    malformed = request_for(contract, now)
    malformed["expected_tree_sha"] = "main"
    with pytest.raises(RunnerBlocked, match="expected_tree_sha"):
        validate_request(malformed, contract, now=now)


def test_environment_does_not_inherit_credentials(tmp_path: Path, monkeypatch):
    monkeypatch.setenv("GITHUB_TOKEN", "must-not-cross-boundary")
    monkeypatch.setenv("AWS_SECRET_ACCESS_KEY", "must-not-cross-boundary")
    environment = sanitized_environment(tmp_path, local_postgres=False)
    assert "GITHUB_TOKEN" not in environment
    assert "AWS_SECRET_ACCESS_KEY" not in environment
    assert environment["PIP_NO_INDEX"] == "1"
    assert environment["GOOGLE_OAUTH_ACCESS_TOKEN"].startswith("aigc-offline")
    assert "NEXUS_TEST_POSTGRES_DSN" not in environment


def test_local_postgres_is_fixed_loopback_only(tmp_path: Path):
    environment = sanitized_environment(tmp_path, local_postgres=True)
    assert environment["NEXUS_TEST_POSTGRES_DSN"] == (
        "postgresql://postgres@127.0.0.1:5432/aigc_test"
    )


def test_contract_rejects_shell_or_arbitrary_executable(tmp_path: Path):
    contract = json.loads(CONTRACT_PATH.read_text(encoding="utf-8"))
    contract["stages"][0]["commands"] = [["bash", "-c", "echo unsafe"]]
    path = tmp_path / "contract.json"
    path.write_text(json.dumps(contract), encoding="utf-8")
    with pytest.raises(RunnerBlocked, match="argv-only"):
        load_contract(path)


def test_dependency_check_accepts_installed_exact_pin(tmp_path: Path):
    version = importlib.metadata.version("pytest")
    requirements = tmp_path / "requirements.txt"
    requirements.write_text(f"pytest=={version}\n", encoding="utf-8")
    result = check_exact_dependencies(requirements)
    assert result["terminal_status"] == "PASS"
    assert result["checked_distributions"] == 1
    assert len(result["manifest_sha256"]) == 64


@pytest.mark.parametrize(
    "entry",
    [
        "pytest>=8",
        "-r another-file.txt",
        "pytest @ https://example.invalid/package.whl",
    ],
)
def test_dependency_check_rejects_non_exact_or_online_entry(
    tmp_path: Path, entry: str
):
    requirements = tmp_path / "requirements.txt"
    requirements.write_text(entry + "\n", encoding="utf-8")
    with pytest.raises(RunnerBlocked, match="not an exact offline pin"):
        check_exact_dependencies(requirements)


def test_dependency_check_rejects_version_drift(tmp_path: Path):
    requirements = tmp_path / "requirements.txt"
    requirements.write_text("pytest==0.0.0\n", encoding="utf-8")
    with pytest.raises(RunnerBlocked, match="does not match exact pin"):
        check_exact_dependencies(requirements)


def test_request_claim_is_one_use(tmp_path: Path):
    now = datetime.now(timezone.utc)
    contract = load_contract(CONTRACT_PATH)
    request = request_for(contract, now)
    claim_request(tmp_path, request)
    with pytest.raises(RunnerBlocked, match="already been consumed"):
        claim_request(tmp_path, request)


def test_execute_contract_records_hashes_without_raw_output(tmp_path: Path):
    candidate = tmp_path / "candidate"
    candidate.mkdir()
    result = tmp_path / "result"
    work = tmp_path / "work"
    contract = {
        "schema_version": "1.0.0",
        "contract_id": "REGENEXCALIBUR-AIGC-FORGERUNNER-V1",
        "external_action_authorized": False,
        "production_activation_authorized": False,
        "provider_call_authorized": False,
        "network_policy": "process_environment_guard",
        "stages": [
            {
                "id": "smoke",
                "timeout_seconds": 30,
                "commands": [["${PYTHON}", "-c", "print('receipt-safe')"]],
            }
        ],
    }
    environment = sanitized_environment(work, local_postgres=False)
    status, records = execute_contract(
        contract,
        candidate_root=candidate,
        result_root=result,
        environment=environment,
        target_sha=FULL_SHA,
        tree_sha=TREE_SHA,
        broker_revision=FULL_SHA,
    )
    assert status == "PASS"
    assert records[0]["status"] == "PASS"
    outcome = records[0]["command_outcomes"][0]
    assert outcome["exit_code"] == 0
    assert "output" not in outcome
    stored = json.loads((result / "stages/smoke.json").read_text())
    assert stored["record_sha256"]
