from __future__ import annotations

from pathlib import Path
import re


ROOT = Path(__file__).resolve().parents[1]
WORKFLOW = ROOT / ".github" / "workflows" / "aigc-ci.yml"


def test_all_actions_are_pinned_to_full_commit_shas() -> None:
    text = WORKFLOW.read_text(encoding="utf-8")
    references = re.findall(r"^\s*uses:\s*([^\s#]+)", text, flags=re.MULTILINE)
    assert references
    for reference in references:
        assert re.fullmatch(r"[^@]+@[a-f0-9]{40}", reference), reference


def test_checkout_credentials_are_not_persisted_and_permissions_are_minimal() -> None:
    text = WORKFLOW.read_text(encoding="utf-8")
    assert "persist-credentials: false" in text
    assert "permissions:\n  contents: read" in text


def test_canonical_validation_artifacts_fail_closed() -> None:
    text = WORKFLOW.read_text(encoding="utf-8")
    assert "if-no-files-found: error" in text
    assert "aigc-colosseum-orchestration-exact-head-" in text
    assert "aigc-locked-validation-" in text


def test_ci_has_bounded_concurrency_and_timeout() -> None:
    text = WORKFLOW.read_text(encoding="utf-8")
    assert "concurrency:" in text
    assert "cancel-in-progress: true" in text
    assert "timeout-minutes: 45" in text
