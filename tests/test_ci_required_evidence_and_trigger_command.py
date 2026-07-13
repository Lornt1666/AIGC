from __future__ import annotations

from pathlib import Path
import re

import pytest


PROJECT_ROOT = Path(__file__).resolve().parents[1]
CI_WORKFLOW_PATH = PROJECT_ROOT / ".github" / "workflows" / "aigc-ci.yml"
TRIGGER_WORKFLOW_PATH = (
    PROJECT_ROOT / ".github" / "workflows" / "aigc_constellation_trigger.yml"
)
TRUSTED_ASSOCIATIONS = {"OWNER", "MEMBER", "COLLABORATOR"}


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def _step_block(workflow: str, step_name: str) -> str:
    marker = f"      - name: {step_name}\n"
    start = workflow.find(marker)
    assert start >= 0, f"workflow step not found: {step_name}"
    next_step = workflow.find("      - name:", start + len(marker))
    return workflow[start:] if next_step < 0 else workflow[start:next_step]


def _configured_issue_comment_command(workflow: str) -> str:
    match = re.search(
        r"github\.event\.comment\.body\s*==\s*'([^']+)'",
        workflow,
    )
    assert match is not None, "issue-comment trigger must use exact command equality"
    return match.group(1)


def _issue_comment_is_eligible(body: str, association: str, workflow: str) -> bool:
    return (
        body == _configured_issue_comment_command(workflow)
        and association in TRUSTED_ASSOCIATIONS
    )


def test_required_ci_evidence_uploads_fail_closed_when_missing() -> None:
    workflow = _read(CI_WORKFLOW_PATH)

    for step_name, expected_path in (
        ("Upload production readiness receipt", "reports/artifacts/production_readiness"),
        ("Upload CI dependency review receipt", "reports/artifacts/ci_dependency_review"),
    ):
        block = _step_block(workflow, step_name)
        assert f"path: {expected_path}" in block
        assert "if-no-files-found: error" in block
        assert "if-no-files-found: warn" not in block
        assert "if-no-files-found: ignore" not in block


def test_issue_comment_trigger_uses_exact_explicit_command() -> None:
    workflow = _read(TRIGGER_WORKFLOW_PATH)

    assert _configured_issue_comment_command(workflow) == "/aigc run"
    assert "contains(github.event.comment.body" not in workflow
    assert "github.event_name == 'workflow_dispatch'" in workflow
    assert "github.event.comment.author_association" in workflow
    for association in sorted(TRUSTED_ASSOCIATIONS):
        assert association in workflow


@pytest.mark.parametrize("association", sorted(TRUSTED_ASSOCIATIONS))
def test_exact_command_is_eligible_for_trusted_associations(association: str) -> None:
    workflow = _read(TRIGGER_WORKFLOW_PATH)

    assert _issue_comment_is_eligible("/aigc run", association, workflow)


@pytest.mark.parametrize(
    "body",
    [
        "AIGC",
        "Please run AIGC",
        "/AIGC RUN",
        "/aigc run now",
        "prefix /aigc run",
        "/aigc run suffix",
        " /aigc run",
        "/aigc run ",
        "/aigc run\nadditional text",
        "/aigc run\n/aigc run",
        "",
    ],
)
def test_non_exact_issue_comment_text_is_rejected(body: str) -> None:
    workflow = _read(TRIGGER_WORKFLOW_PATH)

    assert not _issue_comment_is_eligible(body, "OWNER", workflow)


@pytest.mark.parametrize("association", ["NONE", "FIRST_TIME_CONTRIBUTOR", "CONTRIBUTOR"])
def test_exact_command_is_rejected_for_ineligible_associations(association: str) -> None:
    workflow = _read(TRIGGER_WORKFLOW_PATH)

    assert not _issue_comment_is_eligible("/aigc run", association, workflow)
