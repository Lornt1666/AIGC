from __future__ import annotations

import json
from pathlib import Path

from src.core.contract_validator import validate_file


def test_dual_revision_operator_authorization_is_bounded_and_contract_valid() -> None:
    root = Path(__file__).resolve().parents[1]
    path = (
        root
        / "governance"
        / "receipts"
        / "ci_dual_revision_evidence_v2_operator_authorization.json"
    )
    payload = json.loads(path.read_text(encoding="utf-8"))

    assert payload["operator_identity"] == "Justice Gray Maciocha"
    assert payload["merge_authorized"] is False
    assert payload["deployment_authorized"] is False
    assert payload["credential_use_authorized"] is False
    assert payload["external_action_authorized"] is False
    assert payload["operator_review_required"] is True
    assert payload["rollback_required"] is True
    assert payload["external_action_performed"] is False
    assert validate_file("operator_implementation_authorization", path).valid is True
