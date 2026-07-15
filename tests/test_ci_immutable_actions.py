from __future__ import annotations

from pathlib import Path
import re


ROOT = Path(__file__).resolve().parents[1]
WORKFLOW = ROOT / ".github" / "workflows" / "aigc-ci.yml"


def workflow_text() -> str:
    return WORKFLOW.read_text(encoding="utf-8")


def test_all_third_party_actions_are_pinned_to_full_commits() -> None:
    text = workflow_text()
    references = re.findall(r"^\s*uses:\s*([^\s#]+)", text, flags=re.MULTILINE)

    assert references
    for reference in references:
        assert re.fullmatch(r"[^@]+@[a-f0-9]{40}", reference), reference
    assert "@v4" not in text
    assert "@v5" not in text


def test_checkout_credentials_are_not_persisted() -> None:
    text = workflow_text()

    assert "persist-credentials: false" in text
    assert "permissions:\n  contents: read" in text


def test_required_evidence_uploads_fail_closed() -> None:
    text = workflow_text()

    required_artifacts = (
        "provider-discovery-simulation-${{ github.sha }}",
        "terraform-validation-${{ github.sha }}",
        "test-results-${{ github.sha }}",
        "production-readiness-${{ github.sha }}",
    )
    for artifact in required_artifacts:
        position = text.index(artifact)
        block = text[position : position + 300]
        assert "if-no-files-found: error" in block


def test_ci_has_bounded_concurrency_and_timeout() -> None:
    text = workflow_text()

    assert "concurrency:" in text
    assert "cancel-in-progress: true" in text
    assert "timeout-minutes: 45" in text
