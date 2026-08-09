import json
from copy import deepcopy
from pathlib import Path

import pytest

from scripts.validate_xprize_submission_contract import evaluate


ROOT = Path(__file__).resolve().parents[1]
CONTRACT = ROOT / "config" / "xprize_submission_contract.json"


def payload():
    return json.loads(CONTRACT.read_text(encoding="utf-8"))


def test_current_contract_fails_closed_before_final_submission():
    result = evaluate(payload())
    assert result.ready_for_final_submission is False
    assert result.stale_public_project_copy is True
    assert result.authority_granted is False
    assert 28104 in result.unresolved_field_ids
    assert 27672 in result.unresolved_field_ids
    assert "live_gemini_api_call_evidence" in result.unresolved_deliverables
    assert "submission_zip_file" in result.unresolved_deliverables


def test_required_submission_zip_cannot_be_omitted_from_readiness():
    value = payload()
    for field in value["required_fields"]:
        field["status"] = "EVIDENCED"
    for key in value["deliverables"]:
        value["deliverables"][key] = "EVIDENCED"
    value["deliverables"]["submission_zip_file"] = "MISSING"
    value["project"]["public_copy_alignment"] = "CURRENT"
    value["authority"] = {
        "public_project_update": True,
        "final_submission_update": True,
        "devpost_submission": True,
    }
    result = evaluate(value)
    assert result.ready_for_final_submission is False
    assert "submission_zip_file" in result.unresolved_deliverables


def test_all_fields_and_deliverables_are_required_before_final_readiness():
    value = payload()
    for field in value["required_fields"]:
        field["status"] = "EVIDENCED"
    for key in value["deliverables"]:
        value["deliverables"][key] = "EVIDENCED"
    value["project"]["public_copy_alignment"] = "CURRENT"
    value["authority"] = {
        "public_project_update": True,
        "final_submission_update": True,
        "devpost_submission": True,
    }
    result = evaluate(value)
    assert result.ready_for_final_submission is True


def test_submission_authority_does_not_override_missing_runtime_evidence():
    value = payload()
    value["authority"] = {
        "public_project_update": True,
        "final_submission_update": True,
        "devpost_submission": True,
    }
    result = evaluate(value)
    assert result.ready_for_final_submission is False
    assert result.unresolved_field_ids
    assert result.unresolved_deliverables


def test_evidence_does_not_override_missing_submission_authority():
    value = payload()
    for field in value["required_fields"]:
        field["status"] = "EVIDENCED"
    for key in value["deliverables"]:
        value["deliverables"][key] = "EVIDENCED"
    value["project"]["public_copy_alignment"] = "CURRENT"
    result = evaluate(value)
    assert result.ready_for_final_submission is False
    assert result.authority_granted is False


def test_duplicate_field_id_is_rejected():
    value = payload()
    duplicate = deepcopy(value["required_fields"][0])
    value["required_fields"].append(duplicate)
    with pytest.raises(ValueError, match="duplicate submission field id"):
        evaluate(value)


def test_unknown_status_is_rejected():
    value = payload()
    value["required_fields"][0]["status"] = "I_GUESS_ITS_FINE"
    with pytest.raises(ValueError, match="unsupported field state"):
        evaluate(value)
