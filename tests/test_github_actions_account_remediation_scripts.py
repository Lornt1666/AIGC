from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
BUILDER = ROOT / "scripts" / "build_github_actions_account_remediation_receipt.py"
VERIFIER = ROOT / "scripts" / "verify_github_actions_hosted_recovery.py"
RUNBOOK = ROOT / "docs" / "GITHUB_ACTIONS_ACCOUNT_REMEDIATION_PROCUREMENT.md"


def test_remediation_builder_binds_target_and_tooling_without_authority() -> None:
    text = BUILDER.read_text(encoding="utf-8")

    assert "exact_git_revision" in text
    assert "git_branch" in text
    assert "git_is_ancestor" in text
    assert "git_repository_clean" in text
    assert "target_is_ancestor_of_tooling_revision" in text
    assert "remediation-tooling checkout is not clean" in text
    assert "not an ancestor of the current remediation-tooling checkout" in text
    assert '"merge_authorized": False' in text
    assert '"terraform_apply_authorized": False' in text
    assert '"external_action_performed": False' in text
    assert "terraform apply" not in text
    assert "merge_pull_request" not in text


def test_hosted_recovery_verifier_uses_read_only_github_api() -> None:
    text = VERIFIER.read_text(encoding="utf-8")

    assert '[gh, "api", "--method", "GET", endpoint]' in text
    assert "github_api_mutation_performed" in text
    assert '"merge_authorized": False' in text
    assert '"terraform_apply_authorized": False' in text
    assert '"external_action_performed": False' in text

    forbidden = (
        '"POST"',
        '"PATCH"',
        '"PUT"',
        '"DELETE"',
        "gh run rerun",
        "merge_pull_request",
        "terraform apply",
        "provider mutation",
    )
    for marker in forbidden:
        assert marker not in text


def test_hosted_recovery_verifier_binds_signed_rerun_and_tooling_provenance() -> None:
    text = VERIFIER.read_text(encoding="utf-8")

    assert 'remediation_receipt.get("hosted_rerun_requested") is True' in text
    assert 'signed_run_id = remediation_receipt.get("hosted_rerun_id")' in text
    assert "The GAR receipt is bound to a different hosted rerun ID" in text
    assert "exact_git_revision" in text
    assert "git_branch" in text
    assert "git_is_ancestor" in text
    assert "git_repository_clean" in text
    assert "verification-tooling checkout is not clean" in text
    assert "target_is_ancestor_of_verification_tooling_revision" in text


def test_runbook_preserves_operator_only_account_action_and_later_review() -> None:
    text = RUNBOOK.read_text(encoding="utf-8")

    assert "The repository cannot modify GitHub account billing" in text
    assert "Do not place card numbers" in text
    assert "Prefer rerunning the existing PR #123 workflow" in text
    assert "Closing issue #124 does not approve PR #123" in text
    assert "Do not use that wording before every prerequisite is satisfied" in text
    assert "target PR #123 head" in text
    assert "stacked remediation-tooling branch" in text
    assert "The tooling checkout must be clean before receipt generation" in text
    assert "Remain on a clean approved remediation-tooling branch" in text
