from __future__ import annotations

from collections import Counter
from copy import deepcopy
import json
from pathlib import Path
import re

from jsonschema import Draft202012Validator, ValidationError
import pytest


PROJECT_ROOT = Path(__file__).resolve().parents[1]
WORKFLOW_ROOT = PROJECT_ROOT / ".github" / "workflows"
MANIFEST_PATH = (
    PROJECT_ROOT / "governance" / "ci" / "ci_action_dependency_manifest_v1.json"
)
SCHEMA_PATH = (
    PROJECT_ROOT
    / "governance"
    / "schemas"
    / "ci"
    / "ci_action_dependency_manifest.schema.json"
)
FULL_SHA = re.compile(r"^[0-9a-f]{40}$")
USES_LINE = re.compile(
    r"^\s*uses:\s*[\"']?([^\"'\s#]+)[\"']?",
    re.MULTILINE,
)


def _load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _manifest() -> dict:
    return _load_json(MANIFEST_PATH)


def _schema() -> dict:
    return _load_json(SCHEMA_PATH)


def _workflow_paths() -> list[Path]:
    paths = {
        *WORKFLOW_ROOT.rglob("*.yml"),
        *WORKFLOW_ROOT.rglob("*.yaml"),
    }
    return sorted(paths)


def _external_action_references() -> list[dict[str, str]]:
    references: list[dict[str, str]] = []
    for workflow_path in _workflow_paths():
        workflow = workflow_path.read_text(encoding="utf-8")
        for token in USES_LINE.findall(workflow):
            if token.startswith("./"):
                continue
            if "@" not in token:
                action, revision = token, ""
            else:
                action, revision = token.rsplit("@", 1)
            references.append(
                {
                    "workflow": workflow_path.relative_to(PROJECT_ROOT).as_posix(),
                    "action": action,
                    "revision": revision.lower(),
                }
            )
    return references


def _manifest_actions(payload: dict) -> dict[str, dict]:
    return {entry["action_repository"]: entry for entry in payload["actions"]}


def test_ci_action_dependency_manifest_matches_contract() -> None:
    schema = _schema()
    manifest = _manifest()

    Draft202012Validator.check_schema(schema)
    Draft202012Validator(schema).validate(manifest)


def test_ci_action_manifest_is_unique_and_review_gated() -> None:
    manifest = _manifest()
    repositories = [entry["action_repository"] for entry in manifest["actions"]]

    assert len(repositories) == len(set(repositories)), (
        "each action repository must appear exactly once in the dependency manifest"
    )
    assert manifest["update_policy"] == {
        "require_full_commit_sha": True,
        "reject_unknown_actions": True,
        "operator_review_required": True,
        "automatic_merge_allowed": False,
        "rollback_required": True,
    }
    assert manifest["external_action_performed"] is False


def test_all_workflow_actions_use_full_immutable_commit_shas() -> None:
    workflow_paths = _workflow_paths()
    references = _external_action_references()

    assert workflow_paths, "repository must contain at least one GitHub Actions workflow"
    assert references, "workflows must declare at least one external action"
    for reference in references:
        assert FULL_SHA.fullmatch(reference["revision"]), (
            f"{reference['workflow']}: {reference['action']} must be pinned to a full "
            f"40-character commit SHA; found {reference['revision']!r}"
        )


def test_all_workflow_actions_match_the_dependency_manifest() -> None:
    manifest = _manifest()
    approved = _manifest_actions(manifest)
    references = _external_action_references()
    observed_actions = {reference["action"] for reference in references}

    assert observed_actions == set(approved), (
        "workflow action set changed without a reviewed manifest update: "
        f"observed={sorted(observed_actions)}, approved={sorted(approved)}"
    )

    occurrences = Counter(reference["action"] for reference in references)
    for reference in references:
        expected = approved[reference["action"]]["approved_revision"]
        assert reference["revision"] == expected, (
            f"{reference['workflow']}: {reference['action']} revision changed without "
            "updating the reviewed dependency manifest"
        )

    for action, entry in approved.items():
        assert occurrences[action] == entry["expected_occurrences"], (
            f"{action} occurrence count changed: observed={occurrences[action]}, "
            f"approved={entry['expected_occurrences']}"
        )


def test_manifest_contract_rejects_automatic_merge() -> None:
    manifest = deepcopy(_manifest())
    manifest["update_policy"]["automatic_merge_allowed"] = True

    with pytest.raises(ValidationError):
        Draft202012Validator(_schema()).validate(manifest)


def test_manifest_contract_rejects_mutable_action_revision() -> None:
    manifest = deepcopy(_manifest())
    manifest["actions"][0]["approved_revision"] = "v4"

    with pytest.raises(ValidationError):
        Draft202012Validator(_schema()).validate(manifest)
