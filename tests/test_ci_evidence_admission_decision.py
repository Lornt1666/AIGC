from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
DECISION = ROOT / "docs" / "CI_EVIDENCE_ADMISSION_DECISION.md"


def test_ci_evidence_decision_rejects_fabricated_fallbacks() -> None:
    text = DECISION.read_text(encoding="utf-8")

    assert "not admitted" in text
    assert "masks failed tests and Terraform commands with `|| true`" in text
    assert "fabricates placeholder evidence" in text
    assert "nonexistent `app.simulation` and `app.readiness`" in text
    assert "nonexistent `terraform/staging`" in text


def test_ci_evidence_decision_preserves_canonical_readiness_authority() -> None:
    text = DECISION.read_text(encoding="utf-8")

    assert "config/production_readiness_ledger.json" in text
    assert "src/core/production_readiness_ledger.py" in text
    assert "create a second readiness authority" in text
    assert "68.39" in text
    assert "not 74.50" in text


def test_ci_evidence_decision_keeps_admission_closed() -> None:
    text = DECISION.read_text(encoding="utf-8")

    assert "hosted_ci_replacement: false" in text
    assert "merge_authorized: false" in text
    assert "terraform_apply_performed: false" in text
    assert "external_action_performed: false" in text
