from __future__ import annotations

import json
from pathlib import Path

import pytest

from src.core import ci_merge_candidate_evidence as merge_evidence
from src.core.ci_merge_candidate_evidence import (
    CIMergeCandidateEvidenceError,
    build_receipt,
    validate_receipt,
    verify_merge_candidate,
    write_receipt,
)
from src.core.contract_validator import validate_file


BASE = "a" * 40
HEAD = "b" * 40
MERGE = "c" * 40
OTHER = "d" * 40


def test_build_merge_candidate_receipt_verifies_all_bindings() -> None:
    receipt = build_receipt(
        BASE,
        HEAD,
        MERGE,
        MERGE,
        base_is_ancestor=True,
        head_is_ancestor=True,
    )

    assert receipt["schema_version"] == "2.0.0"
    assert receipt["base_revision"] == BASE
    assert receipt["head_revision"] == HEAD
    assert receipt["actual_revision"] == MERGE
    assert receipt["base_is_ancestor"] is True
    assert receipt["head_is_ancestor"] is True
    assert receipt["verified"] is True
    assert receipt["operator_review_required"] is True
    assert receipt["external_action_performed"] is False


def test_merge_candidate_receipt_records_checkout_mismatch() -> None:
    receipt = build_receipt(
        BASE,
        HEAD,
        MERGE,
        OTHER,
        base_is_ancestor=True,
        head_is_ancestor=True,
    )
    assert receipt["verified"] is False


def test_merge_candidate_receipt_records_missing_ancestry() -> None:
    receipt = build_receipt(
        BASE,
        HEAD,
        MERGE,
        MERGE,
        base_is_ancestor=True,
        head_is_ancestor=False,
    )
    assert receipt["verified"] is False


def test_validate_merge_receipt_rejects_external_action_claim() -> None:
    receipt = build_receipt(
        BASE,
        HEAD,
        MERGE,
        MERGE,
        base_is_ancestor=True,
        head_is_ancestor=True,
    )
    receipt["external_action_performed"] = True
    with pytest.raises(CIMergeCandidateEvidenceError, match="external action"):
        validate_receipt(receipt)


def test_verify_merge_candidate_fails_closed_on_missing_head_ancestry(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(merge_evidence, "read_git_head", lambda _root: MERGE)

    def fake_ancestor(_root: Path, ancestor: str, _descendant: str) -> bool:
        return ancestor == BASE

    monkeypatch.setattr(merge_evidence, "git_is_ancestor", fake_ancestor)

    with pytest.raises(CIMergeCandidateEvidenceError, match="not bound"):
        verify_merge_candidate(tmp_path, BASE, HEAD, MERGE)


def test_written_merge_candidate_receipt_validates_against_contract(tmp_path: Path) -> None:
    output = tmp_path / "ci_merge_candidate_evidence_receipt.json"
    receipt = build_receipt(
        BASE,
        HEAD,
        MERGE,
        MERGE,
        base_is_ancestor=True,
        head_is_ancestor=True,
    )
    write_receipt(receipt, output)

    payload = json.loads(output.read_text(encoding="utf-8"))
    assert payload["verified"] is True
    assert validate_file("ci_merge_candidate_evidence_receipt", output).valid is True
