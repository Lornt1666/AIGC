from __future__ import annotations

import json
from pathlib import Path

from jsonschema import Draft202012Validator

from src.autodesign import AutodesignRequest, run_shadow_autodesign_campaign
from src.autodesign.models import (
    AutodesignCampaignReceipt,
    AutodesignReceipt,
    CHCMBlueprint,
)
from src.core.epistemic.canonicalization import canonical_sha256


ROOT = Path(__file__).resolve().parents[1]


def load(path: str) -> dict[str, object]:
    return json.loads((ROOT / path).read_text(encoding="utf-8"))


def test_generated_autodesign_schemas_match_runtime_contracts():
    expected = {
        "schemas/aigc_regenexcalibur_chcm.schema.json": (
            CHCMBlueprint.model_json_schema()
        ),
        "schemas/aigc_regenexcalibur_autodesign_request.schema.json": (
            AutodesignRequest.model_json_schema()
        ),
        "schemas/aigc_regenexcalibur_autodesign_receipt.schema.json": (
            AutodesignReceipt.model_json_schema()
        ),
        "schemas/aigc_regenexcalibur_autodesign_campaign.schema.json": (
            AutodesignCampaignReceipt.model_json_schema()
        ),
    }
    for path, runtime_schema in expected.items():
        committed_schema = load(path)
        assert committed_schema == runtime_schema
        Draft202012Validator.check_schema(committed_schema)


def test_reference_blueprint_request_and_campaign_validate_against_schemas():
    blueprint = load("config/aigc_regenexcalibur_chcm.v1.json")
    request = load("config/aigc_regenexcalibur_autodesign_request.v1.json")
    campaign = load(
        "reports/artifacts/aigc_regenexcalibur_autodesign_shadow_campaign.json"
    )
    Draft202012Validator(
        load("schemas/aigc_regenexcalibur_chcm.schema.json")
    ).validate(blueprint)
    Draft202012Validator(
        load("schemas/aigc_regenexcalibur_autodesign_request.schema.json")
    ).validate(request)
    Draft202012Validator(
        load("schemas/aigc_regenexcalibur_autodesign_campaign.schema.json")
    ).validate(campaign)


def test_committed_campaign_is_reproducible_hash_valid_and_zero_effect():
    request = AutodesignRequest.model_validate(
        load("config/aigc_regenexcalibur_autodesign_request.v1.json")
    )
    committed = load(
        "reports/artifacts/aigc_regenexcalibur_autodesign_shadow_campaign.json"
    )
    assert committed == run_shadow_autodesign_campaign(request)
    receipt_hash = committed.pop("receipt_sha256")
    assert receipt_hash == canonical_sha256(committed)
    assert committed["terminal_status"] == "BLOCKED"
    assert committed["first_blocker"] == (
        "CAPABILITY_GATE_REQUIRED:CAP-CLOUD-SANDBOX-DEPLOYMENT"
    )
    assert committed["zero_egress"] is True
    assert committed["self_modification_performed"] is False
    assert committed["external_actions_performed"] == 0
    assert committed["authority_granted"] is False


def test_architecture_document_has_required_maps_and_reality_boundary():
    document = (
        ROOT
        / "docs"
        / "architecture"
        / "AIGC_REGENEXCALIBUR_CHCM_AUTODESIGN_V1.md"
    ).read_text(encoding="utf-8")
    assert document.count("```mermaid") >= 3
    for term in (
        "Pantheon Board",
        "High Imperator",
        "Nine Archons",
        "C-suite constellation",
        "POST /v1/autodesign/iterate",
        "OPEN_ENDED_SEQUENCE_OF_TERMINATING_BOUNDED_RUNS",
        "CAPABILITY_GATE_REQUIRED:CAP-CLOUD-SANDBOX-DEPLOYMENT",
    ):
        assert term in document
