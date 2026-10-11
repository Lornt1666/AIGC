from __future__ import annotations

from copy import deepcopy
import json
from pathlib import Path

import pytest

from scripts.validate_xprize_claim_evidence_matrix import evaluate


ROOT = Path(__file__).resolve().parents[1]
MATRIX = ROOT / "config" / "xprize_claim_evidence_matrix.json"


def payload():
    return json.loads(MATRIX.read_text(encoding="utf-8"))


def by_id(value, claim_id):
    return next(item for item in value["claims"] if item["claim_id"] == claim_id)


def test_current_matrix_is_structurally_valid_but_truthfully_unresolved():
    result = evaluate(payload())
    assert result.valid is True
    assert result.claim_count >= 10
    assert "XPRIZE-CLAIM-003" in result.unresolved_claim_ids
    assert "XPRIZE-CLAIM-004" in result.unresolved_claim_ids
    assert "XPRIZE-CLAIM-003" in result.runtime_receipt_blocked_ids
    assert "XPRIZE-CLAIM-007" in result.business_receipt_blocked_ids


def test_proven_claim_requires_verified_evidence():
    value = payload()
    claim = by_id(value, "XPRIZE-CLAIM-001")
    claim["evidence_state"] = "PARTIAL"
    with pytest.raises(ValueError, match="requires VERIFIED evidence"):
        evaluate(value)


def test_live_runtime_claim_cannot_be_promoted_without_runtime_receipt():
    value = payload()
    claim = by_id(value, "XPRIZE-CLAIM-003")
    claim["class"] = "PROVEN"
    claim["evidence_state"] = "VERIFIED"
    with pytest.raises(ValueError, match="runtime claim requires runtime_receipt_ref"):
        evaluate(value)


def test_business_claim_cannot_be_promoted_without_business_receipt():
    value = payload()
    claim = by_id(value, "XPRIZE-CLAIM-007")
    claim["class"] = "PROVEN"
    claim["evidence_state"] = "VERIFIED"
    with pytest.raises(ValueError, match="business claim requires business_receipt_ref"):
        evaluate(value)


def test_implemented_claim_requires_evidence_refs():
    value = payload()
    claim = by_id(value, "XPRIZE-CLAIM-015")
    claim["evidence_refs"] = []
    with pytest.raises(ValueError, match="requires evidence refs"):
        evaluate(value)


def test_missing_evidence_cannot_be_marked_implemented():
    value = payload()
    claim = by_id(value, "XPRIZE-CLAIM-016")
    claim["class"] = "IMPLEMENTED_NOT_RUNTIME_PROVEN"
    with pytest.raises(ValueError, match="cannot have MISSING evidence"):
        evaluate(value)


def test_prohibited_wording_is_required_for_every_material_claim():
    value = payload()
    claim = by_id(value, "XPRIZE-CLAIM-012")
    claim["prohibited_wording"] = []
    with pytest.raises(ValueError, match="prohibited_wording"):
        evaluate(value)


def test_claim_audit_artifact_cannot_assert_external_submission_side_effects():
    value = payload()
    value["devpost_submission_performed"] = True
    with pytest.raises(ValueError, match="must remain false"):
        evaluate(value)


def test_duplicate_claim_id_is_rejected():
    value = payload()
    value["claims"].append(deepcopy(value["claims"][0]))
    with pytest.raises(ValueError, match="duplicate claim_id"):
        evaluate(value)
