from __future__ import annotations

import pytest

from src.core.writable_output_contract import (
    OutputContractError,
    OutputPath,
    validate_output_contract,
)


def test_preflight_creates_and_probes_declared_ephemeral_output(tmp_path):
    result = validate_output_contract(
        tmp_path,
        [OutputPath("phase12", "phase12_observability", "ephemeral")],
    )
    assert len(result) == 1
    assert result[0].writable is True
    assert (tmp_path / "phase12_observability").is_dir()
    assert not list((tmp_path / "phase12_observability").glob(".aigc-write-probe-*"))


@pytest.mark.parametrize("path", ["../outside", "/tmp/outside", "nested/../../outside"])
def test_preflight_rejects_paths_outside_data_root(tmp_path, path):
    with pytest.raises(OutputContractError, match="relative|escapes"):
        validate_output_contract(tmp_path, [OutputPath("unsafe", path, "ephemeral")])


def test_preflight_rejects_duplicate_names_and_paths(tmp_path):
    with pytest.raises(OutputContractError, match="unique"):
        validate_output_contract(
            tmp_path,
            [
                OutputPath("same", "one", "ephemeral"),
                OutputPath("same", "two", "ephemeral"),
            ],
        )
    with pytest.raises(OutputContractError, match="unique"):
        validate_output_contract(
            tmp_path,
            [
                OutputPath("one", "same", "ephemeral"),
                OutputPath("two", "same", "durable"),
            ],
        )


def test_preflight_rejects_file_in_place_of_directory(tmp_path):
    (tmp_path / "not-a-dir").write_text("x", encoding="utf-8")
    with pytest.raises(OutputContractError, match="not a directory"):
        validate_output_contract(
            tmp_path, [OutputPath("broken", "not-a-dir", "ephemeral")]
        )


def test_preflight_requires_existing_data_root(tmp_path):
    with pytest.raises(OutputContractError, match="existing directory"):
        validate_output_contract(
            tmp_path / "missing", [OutputPath("phase", "phase", "ephemeral")]
        )


def test_optional_missing_output_is_not_created(tmp_path):
    result = validate_output_contract(
        tmp_path, [OutputPath("optional", "unused", "ephemeral", required=False)]
    )
    assert result[0].writable is True
    assert not (tmp_path / "unused").exists()
