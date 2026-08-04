from __future__ import annotations

from pathlib import Path


WORKFLOW_PATH = Path(".github/workflows/exact-sha-ci-issue-dispatch.yml")


def workflow_text() -> str:
    return WORKFLOW_PATH.read_text(encoding="utf-8")


def position(text: str, needle: str) -> int:
    observed = text.find(needle)
    assert observed >= 0, f"missing workflow invariant: {needle}"
    return observed


def test_permission_proof_precedes_every_issue_mutation() -> None:
    workflow = workflow_text()
    authority = position(workflow, "- name: Verify requester repository permission and enrich binding")
    authorized_output = position(workflow, 'print("authorized=true")')
    reservation = position(workflow, "- name: Publish and verify unique authorized reservation")
    reservation_comment = position(workflow, 'gh issue comment "$ISSUE_NUMBER" --repo "$GITHUB_REPOSITORY" --body "$marker"')
    completion = position(workflow, "- name: Comment verified completion and close issue")
    failure = position(workflow, "- name: Comment bounded failure")
    assert authority < authorized_output < reservation < reservation_comment < completion < failure


def test_reservation_requires_explicit_authorization_and_emits_reserved_only_after_verification() -> None:
    workflow = workflow_text()
    reservation_header = (
        "- name: Publish and verify unique authorized reservation\n"
        "        id: reservation\n"
        "        if: steps.authority.outputs.authorized == 'true'"
    )
    assert reservation_header in workflow
    verify_position = position(workflow, "--expect-current")
    reserved_position = position(workflow, 'echo "reserved=true" >> "$GITHUB_OUTPUT"')
    assert verify_position < reserved_position


def test_unauthorized_request_cannot_mutate_or_start_target_execution() -> None:
    workflow = workflow_text()
    assert "if: failure() && steps.authority.outputs.authorized == 'true' && steps.reservation.outputs.reserved == 'true'" in workflow
    assert (
        "- name: Verify target exists and is reachable from main\n"
        "        if: steps.authority.outputs.authorized == 'true' && steps.reservation.outputs.reserved == 'true'"
    ) in workflow
    assert (
        "- name: Checkout exact requested target\n"
        "        if: steps.authority.outputs.authorized == 'true' && steps.reservation.outputs.reserved == 'true'"
    ) in workflow


def test_completion_requires_authorization_reservation_upload_and_terminal_revalidation() -> None:
    workflow = workflow_text()
    required_gate = (
        "if: steps.authority.outputs.authorized == 'true' && "
        "steps.reservation.outputs.reserved == 'true' && "
        "steps.upload.outcome == 'success' && "
        "steps.terminal_revalidation.outputs.passed == 'true'"
    )
    completion_start = position(workflow, "- name: Comment verified completion and close issue")
    completion_end = position(workflow, "- name: Post-verify terminal issue and completion marker")
    completion_block = workflow[completion_start:completion_end]
    assert required_gate in completion_block
    assert "gh issue comment" in completion_block
    assert "gh issue close" in completion_block


def test_precheck_is_read_only_and_precedes_authorization() -> None:
    workflow = workflow_text()
    precheck_start = position(workflow, "- name: Revalidate replay state under request lock")
    authority_start = position(workflow, "- name: Verify requester repository permission and enrich binding")
    precheck_block = workflow[precheck_start:authority_start]
    assert "gh api" in precheck_block
    assert "gh issue comment" not in precheck_block
    assert "gh issue close" not in precheck_block
    assert precheck_start < authority_start
