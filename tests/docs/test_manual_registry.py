from __future__ import annotations

from hashlib import sha256
import json
from pathlib import Path

from jsonschema import Draft202012Validator


ROOT = Path(__file__).resolve().parents[2]
REGISTRY_PATH = ROOT / "governance" / "manuals" / "manual_registry.json"
SCHEMA_PATH = ROOT / "governance" / "schemas" / "manuals" / "manual_registry.schema.json"


def _load(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def test_manual_registry_is_schema_valid() -> None:
    schema = _load(SCHEMA_PATH)
    registry = _load(REGISTRY_PATH)
    Draft202012Validator.check_schema(schema)
    errors = sorted(
        Draft202012Validator(schema).iter_errors(registry),
        key=lambda item: list(item.absolute_path),
    )
    assert not errors, [error.message for error in errors]


def test_registered_hashed_artifacts_exist_and_match() -> None:
    registry = _load(REGISTRY_PATH)
    for artifact in registry["artifacts"]:
        expected = artifact.get("sha256")
        if expected is None:
            continue
        path_value = artifact.get("path")
        if artifact.get("storage_status") == "VERIFIED_NOT_COMMITTED":
            assert path_value is None
            continue
        assert isinstance(path_value, str)
        path = ROOT / path_value
        assert path.is_file(), path_value
        assert sha256(path.read_bytes()).hexdigest() == expected


def test_compiled_editions_are_non_authoritative() -> None:
    registry = _load(REGISTRY_PATH)
    compiled = [
        artifact
        for artifact in registry["artifacts"]
        if artifact["kind"] in {
            "COMPILED_EDITABLE_PUBLICATION",
            "COMPILED_FIXED_LAYOUT_PUBLICATION",
        }
    ]
    assert len(compiled) == 2
    assert all(
        artifact["authority"] == "NON_AUTHORITATIVE_RELEASE_ARTIFACT"
        for artifact in compiled
    )


def test_missing_package_sources_are_explicit_and_not_fabricated() -> None:
    registry = _load(REGISTRY_PATH)
    missing = registry["missing_source_artifacts"]
    assert len(missing) == 23
    assert all(item["status"] == "NOT_PROVIDED_IN_UPLOAD" for item in missing)
    for item in missing:
        canonical_candidate = ROOT / "docs" / "manuals" / "books" / Path(item["path"]).name
        assert not canonical_candidate.exists()


def test_manual_index_links_resolve() -> None:
    index = (ROOT / "docs" / "manuals" / "AIGC_MANUAL_INDEX.md").read_text(encoding="utf-8")
    expected_paths = [
        "research/AIGC_GAME_MANUAL_RESEARCH_SYNTHESIS.md",
        "prompts/AIGC_MASTER_BOOKFORGE_PROMPT.md",
        "releases/2026-07-11/README.md",
        "source/AIGC_DOCS_INDEX_SNAPSHOT_2026_07_11.md",
    ]
    for relative in expected_paths:
        assert f"]({relative})" in index
        assert (ROOT / "docs" / "manuals" / relative).exists()


def test_manual_sources_do_not_contain_tool_citation_tokens() -> None:
    paths = [
        ROOT / "docs" / "manuals" / "AIGC_MANUAL_INDEX.md",
        ROOT / "docs" / "manuals" / "research" / "AIGC_GAME_MANUAL_RESEARCH_SYNTHESIS.md",
        ROOT / "docs" / "manuals" / "prompts" / "AIGC_MASTER_BOOKFORGE_PROMPT.md",
    ]
    forbidden = ("filecite", "cite", "turn58file")
    for path in paths:
        text = path.read_text(encoding="utf-8")
        assert not any(token in text for token in forbidden), path
