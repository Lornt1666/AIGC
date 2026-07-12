from __future__ import annotations

from collections import Counter
from pathlib import Path
import re


WORKFLOW_PATH = (
    Path(__file__).resolve().parents[1] / ".github" / "workflows" / "aigc-ci.yml"
)
FULL_SHA = re.compile(r"^[0-9a-f]{40}$")
USES = re.compile(r"^\s*uses:\s+([^@\s]+)@([^\s#]+)", re.MULTILINE)

APPROVED_ACTION_REVISIONS = {
    "actions/checkout": "34e114876b0b11c390a56381ad16ebd13914f8d5",
    "actions/setup-python": "a26af69be951a213d495a4c3e4e4022e16d87065",
    "actions/upload-artifact": "ea165f8d65b6e75b540449e92b4886f43607fa02",
}

EXPECTED_USAGE_COUNTS = Counter(
    {
        "actions/checkout": 2,
        "actions/setup-python": 2,
        "actions/upload-artifact": 2,
    }
)


def _external_action_references() -> list[tuple[str, str]]:
    workflow = WORKFLOW_PATH.read_text(encoding="utf-8")
    return [
        (action, revision.lower())
        for action, revision in USES.findall(workflow)
        if not action.startswith("./")
    ]


def test_all_third_party_actions_use_full_immutable_commit_shas() -> None:
    references = _external_action_references()

    assert references, "CI workflow must declare at least one external action"
    for action, revision in references:
        assert FULL_SHA.fullmatch(revision), (
            f"{action} must be pinned to a full 40-character commit SHA; "
            f"found {revision!r}"
        )


def test_ci_action_pins_match_the_reviewed_allowlist() -> None:
    references = _external_action_references()
    observed_counts = Counter(action for action, _revision in references)

    assert observed_counts == EXPECTED_USAGE_COUNTS
    for action, revision in references:
        assert action in APPROVED_ACTION_REVISIONS, f"Unreviewed action: {action}"
        assert revision == APPROVED_ACTION_REVISIONS[action], (
            f"{action} revision changed without updating the reviewed allowlist"
        )
