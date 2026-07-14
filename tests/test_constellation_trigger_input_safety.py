from __future__ import annotations

from pathlib import Path
import re


PROJECT_ROOT = Path(__file__).resolve().parents[1]
WORKFLOW_PATH = PROJECT_ROOT / ".github" / "workflows" / "aigc_constellation_trigger.yml"


def _workflow_text() -> str:
    return WORKFLOW_PATH.read_text(encoding="utf-8")


def _run_blocks(workflow: str) -> list[str]:
    lines = workflow.splitlines()
    blocks: list[str] = []
    current: list[str] | None = None
    run_indent = -1

    for line in lines:
        match = re.match(r"^(\s*)run:\s*(.*)$", line)
        if match:
            if current is not None:
                blocks.append("\n".join(current))
            run_indent = len(match.group(1))
            current = [match.group(2)]
            continue

        if current is None:
            continue

        stripped = line.strip()
        indent = len(line) - len(line.lstrip())
        if stripped and indent <= run_indent:
            blocks.append("\n".join(current))
            current = None
            run_indent = -1
            continue
        current.append(line)

    if current is not None:
        blocks.append("\n".join(current))
    return blocks


def test_issue_comment_trigger_requires_trusted_author_association() -> None:
    workflow = _workflow_text()

    assert "github.event.comment.author_association" in workflow
    assert "OWNER" in workflow
    assert "MEMBER" in workflow
    assert "COLLABORATOR" in workflow


def test_untrusted_event_values_are_not_interpolated_into_shell_blocks() -> None:
    shell_text = "\n".join(_run_blocks(_workflow_text()))

    assert "github.event.comment.body" not in shell_text
    assert "github.event.inputs." not in shell_text
    assert "cat > aigc_trigger.env" not in shell_text
    assert ". ./aigc_trigger.env" not in shell_text


def test_event_values_enter_through_job_environment_and_are_shell_quoted() -> None:
    workflow = _workflow_text()

    assert (
        "AIGC_TRIGGER_TEXT: ${{ github.event.inputs.narration || "
        "github.event.comment.body || 'AIGC manual trigger' }}"
    ) in workflow
    assert "AIGC_PROJECT_PROFILE: ${{ github.event.inputs.project_profile || 'auto' }}" in workflow
    assert "AIGC_RUN_MODE: ${{ github.event.inputs.run_mode || 'artifact_generation' }}" in workflow
    assert "AIGC_SUBMISSION_DECISION: ${{ github.event.inputs.submission_decision || 'review_only' }}" in workflow
    assert "AIGC_SUBMISSION_PHRASE: ${{ github.event.inputs.submission_phrase || '' }}" in workflow

    assert '--trigger-text "$AIGC_TRIGGER_TEXT"' in workflow
    assert '--project-profile "$AIGC_PROJECT_PROFILE"' in workflow
    assert '--run-mode "$AIGC_RUN_MODE"' in workflow
    assert '--decision "$AIGC_SUBMISSION_DECISION"' in workflow
    assert '--phrase "$AIGC_SUBMISSION_PHRASE"' in workflow
