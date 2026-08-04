from __future__ import annotations

from hashlib import sha256
import json
from pathlib import Path

import pytest

from scripts.validate_exact_sha_ci_issue_request import (
    COMPLETION_MARKER,
    REQUIRED_CHECKS,
    canonical,
    validate_issue,
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
    return "\n".join(
        [
            "### Request JSON",
            "```json",
            json.dumps(value, sort_keys=True),
            "```",
            "### Authority confirmation",
            "- [x] I confirm production activation is not authorized.",
            "- [x] I confirm no external provider action is authorized.",
            "- [x] I confirm this issue contains no credentials or secrets.",
        ]
    )


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
    return {
        "action": action,
        "sender": {"login": "Lornt1666", "id": 236225491},
    }


def test_valid_issue_binds_identity_timestamps_body_request_and_target():
    envelope = validate_issue(event(), issue(), [], BROKER)
    binding = envelope["binding"]
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


@pytest.mark.parametrize(
    "field,value",
    [
        ("target_sha", "main"),
        ("broker_revision", "main"),
        ("production_activation_authorized", True),
        ("external_action_authorized", True),
        ("repository", "other/repo"),
        ("target_branch", "feature"),
    ],
)
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


def test_completed_issue_replay_is_rejected():
    comments = [{"body": f"{COMPLETION_MARKER} request_id={request()['request_id']}"}]
    with pytest.raises(ValueError, match="already completed"):
        validate_issue(event(), issue(), comments, BROKER)


def test_issue_edit_or_label_change_after_validation_fails_closed():
    initial = issue()
    envelope = validate_issue(event(), initial, [], BROKER)
    edited = dict(initial)
    edited["updated_at"] = "2026-08-04T00:01:00Z"
    edited["body"] = initial["body"] + "\nchanged"
    with pytest.raises(ValueError, match="changed"):
        verify_unchanged(edited, envelope)
    relabeled = dict(initial)
    relabeled["labels"] = []
    with pytest.raises(ValueError, match="label"):
        verify_unchanged(relabeled, envelope)


def test_workflow_is_default_branch_controlled_minimal_and_pinned():
    workflow = Path(".github/workflows/exact-sha-ci-issue-dispatch.yml").read_text(encoding="utf-8")
    assert "issues:" in workflow
    assert "types:" in workflow and "opened" in workflow and "labeled" in workflow
    assert "contents: read" in workflow
    assert "issues: write" in workflow
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
