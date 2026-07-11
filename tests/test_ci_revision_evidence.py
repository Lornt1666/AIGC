from __future__ import annotations

import json
from pathlib import Path

import pytest

from src.core import ci_revision_evidence as revision_evidence
from src.core.ci_revision_evidence import (
    CIRevisionEvidenceError,
    build_receipt,
    normalize_event_name,
    normalize_revision,
    verify_ci_revision,
    write_receipt,
)
from src.core.contract_validator import validate_file


REVISION_A = "a" * 40
REVISION_B = "b" * 40


def test_build_receipt_verifies_matching_exact_revision() -> None:
    receipt = build_receipt(REVISION_A, REVISION_A, "pull_request")

    assert receipt["expected_revision"] == REVISION_A
    assert receipt["actual_revision"] == REVISION_A
    assert receipt["verified"] is True
    assert receipt["evidence_class"] == "exact_checked_out_revision"
    assert receipt["operator_review_required"] is True
    assert receipt["external_action_performed"] is False


def test_build_receipt_records_mismatch_without_fabricating_success() -> None:
    receipt = build_receipt(REVISION_A, REVISION_B, "push")

    assert receipt["verified"] is False
    assert receipt["expected_revision"] != receipt["actual_revision"]


def test_revision_normalization_is_strict() -> None:
    assert normalize_revision(REVISION_A.upper(), "revision") == REVISION_A
    with pytest.raises(CIRevisionEvidenceError):
        normalize_revision("abc123", "revision")
    with pytest.raises(CIRevisionEvidenceError):
        normalize_revision("g" * 40, "revision")


def test_unknown_event_is_bounded() -> None:
    assert normalize_event_name("pull_request") == "pull_request"
    assert normalize_event_name("unexpected_event") == "unknown"


def test_verify_ci_revision_fails_closed_on_mismatch(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(revision_evidence, "read_git_head", lambda _root: REVISION_B)

    with pytest.raises(CIRevisionEvidenceError, match="CI revision mismatch"):
        verify_ci_revision(tmp_path, REVISION_A, "pull_request")


def test_written_receipt_validates_against_contract(tmp_path: Path) -> None:
    output = tmp_path / "ci_revision_evidence_receipt.json"
    receipt = build_receipt(REVISION_A, REVISION_A, "workflow_dispatch")

    write_receipt(receipt, output)

    assert json.loads(output.read_text(encoding="utf-8"))["verified"] is True
    result = validate_file("ci_revision_evidence_receipt", output)
    assert result.valid is True


def test_workflow_wires_exact_revision_checkout_and_readiness_binding() -> None:
    workflow = (Path(__file__).resolve().parents[1] / ".github" / "workflows" / "aigc-ci.yml").read_text(
        encoding="utf-8"
    )

    assert "github.event.pull_request.head.sha || github.sha" in workflow
    assert "ref: ${{ env.AIGC_EXPECTED_REVISION }}" in workflow
    assert "python src/ci_revision_evidence_cli.py" in workflow
    assert 'GITHUB_SHA="$AIGC_EXPECTED_REVISION" python src/aigc.py readiness' in workflow
    assert "reports/artifacts/ci_revision_evidence" in workflow
