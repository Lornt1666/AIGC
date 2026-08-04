from pathlib import Path


WORKFLOW = Path(".github/workflows/exact-sha-ci-issue-dispatch.yml")


def test_private_target_reachability_uses_authenticated_read_only_api() -> None:
    workflow = WORKFLOW.read_text(encoding="utf-8")
    assert 'gh api "repos/${GITHUB_REPOSITORY}/git/commits/${TARGET_SHA}"' in workflow
    assert 'gh api "repos/${GITHUB_REPOSITORY}/compare/${TARGET_SHA}...main"' in workflow
    assert 'merge_base != target_sha' in workflow
    assert 'comparison.get("status") not in {"ahead", "identical"}' in workflow
    assert 'git fetch --no-tags origin main "$TARGET_SHA"' not in workflow
    assert "persist-credentials: false" in workflow


def test_reachability_check_precedes_exact_checkout() -> None:
    workflow = WORKFLOW.read_text(encoding="utf-8")
    reachability = workflow.index("- name: Verify target exists and is reachable from main")
    checkout = workflow.index("- name: Checkout exact requested target")
    assert reachability < checkout
