from __future__ import annotations

from hashlib import sha256
import json
from pathlib import Path

import pytest

from scripts.validate_exact_sha_ci_issue_request import (
    COMPLETION_MARKER,
    REQUIRED_CHECKS,
    RESERVATION_MARKER,
    canonical,
    validate_issue,
    verify_reservation_state,
    verify_unchanged,
)

BROKER = "b" * 40
TARGET = "a" * 40


def request() -> dict:
    return {
        "schema_version": "1.0.0",
        "request_id": "CI-RECEIPT-BA6110A-0001",
        "repository": "Lornt1666/AIGC",
        "target_branch": "main",
        "target_sha": TARGET,
        "broker_revision": BROKER,
        "requested_checks": sorted(REQUIRED_CHECKS),
        "production_activation_authorized": False,
        "external_action_authorized": False,
    }


def body(value: dict | None = None) -> str:
    value = value or request()
    return "\n".join([
        "### Request JSON",
        "```json",
        json.dumps(value, sort_keys=True),
        "```",
        "### Authority confirmation",
        "- [x] I confirm production activation is not authorized.",
        "- [x] I confirm no external provider action is authorized.",
        "- [x] I confirm this issue contains no credentials or secrets.",
    ])


def issue(value: dict | None = None) -> dict:
    return {
        "number": 77,
        "node_id": "I_kwDOexample",
        "state": "open",
        "created_at": "2026-08-04T00:00:00Z",
        "updated_at": "2026-08-04T00:00:00Z",
        "author_association": "OWNER",
        "body": body(value),
        "user": {"login": "Lornt1666", "id": 236225491},
        "labels": [{"name": "exact-sha-ci-request"}],
    }


def event(action: str = "opened") -> dict:
    return {"action": action, "sender": {"login": "Lornt1666", "id": 236225491}}


def envelope(action: str = "opened") -> dict:
    return validate_issue(event(action), issue(), [], BROKER)


def reservation(run_id: str) -> dict:
    return {"body": f"{RESERVATION_MARKER} request_id={request()['request_id']} run_id={run_id}"}


def completion(run_id: str) -> dict:
    return {"body": f"{COMPLETION_MARKER} request_id={request()['request_id']} run_id={run_id}"}


def test_valid_issue_binds_identity_timestamps_body_request_and_target():
    value = envelope()
    binding = value["binding"]
    assert binding["issue_number"] == 77
    assert binding["actor_id"] == 236225491
    assert binding["target_sha"] == TARGET
    assert binding["broker_revision"] == BROKER
    assert binding["request_sha256"] == sha256(canonical(request())).hexdigest()
    unsigned = dict(binding)
    observed = unsigned.pop("execution_binding_sha256")
    assert sha256(canonical(unsigned)).hexdigest() == observed


@pytest.mark.parametrize("association", ["NONE", "FIRST_TIME_CONTRIBUTOR", "CONTRIBUTOR"])
def test_unauthorized_issue_author_is_rejected(association):
    value = issue()
    value["author_association"] = association
    with pytest.raises(ValueError, match="authority"):
        validate_issue(event(), value, [], BROKER)


def test_event_actor_must_match_issue_author():
    value = event()
    value["sender"] = {"login": "other", "id": 2}
    with pytest.raises(ValueError, match="actor"):
        validate_issue(value, issue(), [], BROKER)


@pytest.mark.parametrize("field,value", [
    ("target_sha", "main"),
    ("broker_revision", "main"),
    ("production_activation_authorized", True),
    ("external_action_authorized", True),
    ("repository", "other/repo"),
    ("target_branch", "feature"),
])
def test_request_rejects_target_authority_and_repository_drift(field, value):
    data = request()
    data[field] = value
    with pytest.raises(ValueError):
        validate_issue(event(), issue(data), [], BROKER)


def test_request_rejects_arbitrary_fields_and_commands():
    data = request()
    data["command"] = "curl example.invalid"
    with pytest.raises(ValueError, match="closed contract"):
        validate_issue(event(), issue(data), [], BROKER)


def test_secret_like_material_is_rejected():
    value = issue()
    secret_field = "access" + "_token"
    value["body"] += f"\n{secret_field}: forbidden-value"
    with pytest.raises(ValueError, match="secret"):
        validate_issue(event(), value, [], BROKER)


def test_completed_issue_replay_is_rejected_at_initial_validation():
    comments = [{"body": f"{COMPLETION_MARKER} request_id={request()['request_id']}"}]
    with pytest.raises(ValueError, match="already completed"):
        validate_issue(event(), issue(), comments, BROKER)


def test_issue_edit_or_label_change_after_validation_fails_closed():
    initial = issue()
    value = envelope()
    comment_only_change = dict(initial)
    comment_only_change["updated_at"] = "2026-08-04T00:01:00Z"
    verify_unchanged(comment_only_change, value)
    edited = dict(initial)
    edited["body"] = initial["body"] + "\nchanged"
    with pytest.raises(ValueError, match="changed"):
        verify_unchanged(edited, value)
    relabeled = dict(initial)
    relabeled["labels"] = []
    with pytest.raises(ValueError, match="label"):
        verify_unchanged(relabeled, value)


def test_opened_and_labeled_events_share_one_reservation_state():
    opened = envelope("opened")
    labeled = envelope("labeled")
    assert opened["request"] == labeled["request"]
    assert opened["binding"]["issue_number"] == labeled["binding"]["issue_number"]
    verify_reservation_state(issue(), [], opened, "1001", expect_current=False)
    existing = [reservation("1001")]
    with pytest.raises(ValueError, match="already has a reservation"):
        verify_reservation_state(issue(), existing, labeled, "1002", expect_current=False)


def test_queued_same_issue_run_rejects_existing_current_issue_reservation():
    value = envelope()
    with pytest.raises(ValueError, match="already has a reservation"):
        verify_reservation_state(issue(), [reservation("1001")], value, "1002", expect_current=False)


def test_foreign_or_duplicate_reservation_is_rejected_after_publication():
    value = envelope()
    with pytest.raises(ValueError, match="exactly one current-run"):
        verify_reservation_state(issue(), [reservation("other")], value, "1001", expect_current=True)
    with pytest.raises(ValueError, match="exactly one current-run"):
        verify_reservation_state(
            issue(),
            [reservation("1001"), reservation("1001")],
            value,
            "1001",
            expect_current=True,
        )


def test_completed_request_is_rejected_before_or_after_reservation():
    value = envelope()
    with pytest.raises(ValueError, match="completion marker"):
        verify_reservation_state(issue(), [completion("900")], value, "1001", expect_current=False)
    with pytest.raises(ValueError, match="completion marker"):
        verify_reservation_state(
            issue(),
            [reservation("1001"), completion("900")],
            value,
            "1001",
            expect_current=True,
        )


def test_exactly_one_current_run_reservation_allows_one_execution():
    verify_reservation_state(
        issue(),
        [reservation("1001")],
        envelope(),
        "1001",
        expect_current=True,
    )


def test_workflow_is_default_branch_controlled_minimal_and_pinned():
    workflow = Path(".github/workflows/exact-sha-ci-issue-dispatch.yml").read_text(encoding="utf-8")
    assert "issues:" in workflow and "opened" in workflow and "labeled" in workflow
    assert "permissions: {}" in workflow
    assert "contents: read" in workflow and "issues: write" in workflow
    assert "contents: write" not in workflow
    assert "actions: write" not in workflow
    assert "id-token: write" not in workflow
    assert "pull-requests: write" not in workflow
    assert "github.workflow_sha" in workflow
    assert "persist-credentials: false" in workflow
    assert "terraform apply" not in workflow
    assert "gmail.send" not in workflow
    assert "--execution-envelope" in workflow
    assert "--verify-inventory" in workflow
    assert "gh issue close" in workflow
    assert "if: failure()" in workflow
    for marker in (
        "actions/checkout@",
        "actions/setup-python@",
        "actions/upload-artifact@",
        "hashicorp/setup-terraform@",
    ):
        for line in (line.strip() for line in workflow.splitlines() if marker in line):
            revision = line.split("@", 1)[1]
            assert len(revision) == 40 and all(character in "0123456789abcdef" for character in revision)


def test_workflow_serializes_rechecks_authorizes_reserves_and_post_verifies():
    workflow = Path(".github/workflows/exact-sha-ci-issue-dispatch.yml").read_text(encoding="utf-8")
    assert "validate-request:" in workflow and "execute-request:" in workflow
    assert "group: exact-sha-ci-request-${{ needs.validate-request.outputs.request_id }}" in workflow
    precheck = workflow.index("Revalidate replay state under request lock")
    authority = workflow.index("Verify requester repository permission and enrich binding")
    reservation_step = workflow.index("Publish and verify unique authorized reservation")
    assert precheck < authority < reservation_step
    assert "current-comments-before.json" in workflow
    assert "current-comments-after.json" in workflow
    assert "--expect-current" in workflow
    assert "--paginate --slurp" in workflow and "jq 'add'" in workflow
    assert "AIGC-EXACT-SHA-CI-RESERVED" in workflow
    assert "/collaborators/${AUTHOR}/permission" in workflow
    assert '"push" if raw_permission == "write"' in workflow
    assert 'permission not in {"push", "maintain", "admin"}' in workflow
    assert 'binding["repository_permission"]' in workflow
    assert 'print("authorized=true")' in workflow
    assert "if: steps.authority.outputs.authorized == 'true'" in workflow
    assert 'echo "reserved=true" >> "$GITHUB_OUTPUT"' in workflow
    assert "steps.upload.outputs.artifact-id" in workflow
    assert "steps.upload.outputs.artifact-url" in workflow
    assert "steps.upload.outputs.artifact-digest" in workflow
    assert "Post-verify terminal issue and completion marker" in workflow
    assert "terminal request label is absent" in workflow
    assert "exact terminal completion marker was not verified" in workflow


def test_issue_form_and_label_contract_are_closed_and_non_authorizing():
    form = Path(".github/ISSUE_TEMPLATE/exact-sha-ci-request.yml").read_text(encoding="utf-8")
    contract = json.loads(Path("config/exact_sha_ci_issue_label_contract.json").read_text())
    assert "exact-sha-ci-request" in form
    assert "render: json" in form
    assert contract["required_permissions"] == {"contents": "read", "issues": "write"}
    assert contract["production_activation_authorized"] is False
    assert contract["external_action_authorized"] is False


def test_receipt_builder_digest_covers_optional_issue_envelope():
    source = Path("scripts/build_exact_sha_ci_receipt.py").read_text(encoding="utf-8")
    assert "validate_execution_envelope" in source
    assert "issue_execution_binding_sha256" in source
    assert "issue_request_envelope.json" in source
    assert "execution_binding_sha256" in source
    assert "verify_inventory(args.output_root)" in source
