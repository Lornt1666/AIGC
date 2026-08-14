from __future__ import annotations

from copy import deepcopy
import json
from pathlib import Path

import pytest
from jsonschema import Draft202012Validator, FormatChecker
from pydantic import ValidationError

from scripts.validate_aigc_occupation_packs import validate_pack_directory
from src.core.nexus.occupation_registry import load_occupation_packs
from src.domain.nexus.occupation import OccupationPack


ROOT = Path(__file__).resolve().parents[1]
PACK_DIRECTORY = ROOT / "config" / "occupation_packs"
SCHEMA_PATH = ROOT / "schemas" / "aigc_occupation_pack.schema.json"
SCHEMA = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))


def test_expanded_pack_catalogue_validates_but_does_not_self_certify():
    report = validate_pack_directory(PACK_DIRECTORY, SCHEMA_PATH)
    assert report["status"] == "PASS"
    assert report["pack_count"] >= 13
    assert report["certified_pack_count"] == 0
    assert report["external_authority_granted"] is False
    assert report["external_action_performed"] is False
    packs = load_occupation_packs()
    assert {item.status for item in packs} == {"DRAFT"}
    assert all(item.grants_external_authority is False for item in packs)
    assert all(item.autonomy_ceiling == "LOCAL_DRAFT_ONLY" for item in packs)
    assert all(item.classification_mappings for item in packs)


def test_pack_catalogue_covers_requested_digital_work_families():
    expected = {
        "OCC-DEEP_RESEARCH_ANALYST",
        "OCC-TECHNICAL_WRITER",
        "OCC-SOFTWARE_QA_ANALYST",
        "OCC-CUSTOMER_SUPPORT_KNOWLEDGE",
        "OCC-PROJECT_COORDINATOR",
        "OCC-BOOKKEEPING_WORKPAPER",
        "OCC-DEFENSIVE_CYBERSECURITY_ANALYST",
        "OCC-PROCUREMENT_RESEARCH_ANALYST",
        "OCC-EXECUTIVE_OPERATIONS_ASSISTANT",
        "OCC-EDITORIAL_CONTENT_ASSISTANT",
    }
    observed = {item.pack_id for item in load_occupation_packs()}
    assert expected <= observed


def test_schema_is_closed_and_requires_training_rights_gate():
    Draft202012Validator.check_schema(SCHEMA)
    value = json.loads((PACK_DIRECTORY / "software_research_assistant.json").read_text())
    value["raw_secret"] = "must-not-pass"
    errors = list(Draft202012Validator(SCHEMA, format_checker=FormatChecker()).iter_errors(value))
    assert errors

    value.pop("raw_secret")
    value["training_rights_required"] = False
    errors = list(Draft202012Validator(SCHEMA, format_checker=FormatChecker()).iter_errors(value))
    assert errors


def test_certification_cannot_be_self_asserted_without_complete_validity():
    value = json.loads((PACK_DIRECTORY / "software_research_assistant.json").read_text())
    value["status"] = "CERTIFIED"
    with pytest.raises(ValidationError, match="requires issuer and validity"):
        OccupationPack.model_validate(value)


def test_noncertified_pack_cannot_carry_issuer_or_validity_claims():
    value = json.loads((PACK_DIRECTORY / "administrative_coordinator.json").read_text())
    value["certification_issuer"] = "self"
    with pytest.raises(ValidationError, match="cannot carry certification"):
        OccupationPack.model_validate(value)


def test_duplicate_capability_ids_are_rejected():
    value = json.loads((PACK_DIRECTORY / "data_analysis_reporting.json").read_text())
    duplicate = deepcopy(value["capabilities"][0])
    value["capabilities"].append(duplicate)
    with pytest.raises(ValidationError, match="must be unique"):
        OccupationPack.model_validate(value)


def test_unresolved_classification_cannot_claim_a_code():
    value = json.loads((PACK_DIRECTORY / "software_research_assistant.json").read_text())
    value["classification_mappings"][0]["mapping_status"] = "UNRESOLVED"
    with pytest.raises(ValidationError, match="must not claim a code"):
        OccupationPack.model_validate(value)


def test_draft_pack_cannot_claim_certified_execution_autonomy():
    value = json.loads((PACK_DIRECTORY / "administrative_coordinator.json").read_text())
    value["autonomy_ceiling"] = "CERTIFIED_BOUNDED_EXECUTION"
    with pytest.raises(ValidationError, match="cannot exceed local draft autonomy"):
        OccupationPack.model_validate(value)
