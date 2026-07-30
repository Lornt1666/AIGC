from __future__ import annotations

import json
import os
from pathlib import Path

import pytest

from src.core.financial_evidence import prepare_financial_evidence_packet
from src.dashboard import financial_evidence_panel as panel


ROOT = Path(__file__).resolve().parents[1]


def _example_config() -> dict:
    return json.loads(
        (ROOT / "config" / "financial_evidence.example.json").read_text(
            encoding="utf-8"
        )
    )


def _write_private_json(tmp_path: Path, name: str, payload: dict) -> Path:
    private_root = tmp_path / "private-evidence"
    private_root.mkdir(mode=0o700, exist_ok=True)
    private_root.chmod(0o700)
    config_path = private_root / name
    config_path.write_text(
        json.dumps(payload, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    config_path.chmod(0o600)
    return config_path


def _write_external_config(tmp_path: Path) -> Path:
    return _write_private_json(
        tmp_path,
        "financial-evidence.json",
        _example_config(),
    )


def _compliance_config(financial_packet_id: str) -> dict:
    config = json.loads(
        (
            ROOT / "config" / "canadian_compliance_workflow.example.json"
        ).read_text(encoding="utf-8")
    )
    financial = _example_config()
    config["tenant_id"] = financial["tenant_id"]
    config["engagement_id"] = financial["engagement_id"]
    config["as_of_date"] = financial["as_of_date"]
    config["financial_evidence_packet_id"] = financial_packet_id
    return config


def test_disabled_by_default_returns_before_any_file_access(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    monkeypatch.delenv(panel.FEATURE_FLAG, raising=False)
    monkeypatch.delenv(panel.FINANCIAL_CONFIG_ENV, raising=False)

    def forbidden_file_access(*_args: object, **_kwargs: object) -> Path:
        raise AssertionError("disabled panel attempted file access")

    monkeypatch.setattr(
        panel,
        "load_financial_evidence_config",
        forbidden_file_access,
    )

    state = panel.load_local_financial_projection(tmp_path, {})

    assert state == {
        "status": "disabled",
        "financial_packet": None,
        "compliance_packet": None,
    }


def test_enabled_without_financial_path_requires_configuration(
) -> None:
    state = panel.load_local_financial_projection(
        ROOT,
        {panel.FEATURE_FLAG: "true"},
    )

    assert state == {
        "status": "configuration_required",
        "financial_packet": None,
        "compliance_packet": None,
    }


def test_relative_private_config_path_is_rejected(tmp_path: Path) -> None:
    with pytest.raises(ValueError):
        panel.load_local_financial_projection(
            ROOT,
            {
                panel.FEATURE_FLAG: "1",
                panel.FINANCIAL_CONFIG_ENV: "private/financial.json",
            },
        )


def test_config_inside_repository_is_rejected_after_symlink_resolution(
    tmp_path: Path,
) -> None:
    in_repository = ROOT / "config" / "financial_evidence.example.json"
    alias = tmp_path / "external-looking-alias.json"
    try:
        alias.symlink_to(in_repository)
    except (NotImplementedError, OSError) as exc:
        pytest.skip(f"symlinks unavailable in this test environment: {exc}")

    assert alias.resolve(strict=True) == in_repository.resolve(strict=True)
    with pytest.raises(ValueError):
        panel.load_local_financial_projection(
            ROOT,
            {
                panel.FEATURE_FLAG: "yes",
                panel.FINANCIAL_CONFIG_ENV: str(alias),
            },
        )


def test_external_synthetic_config_loads_as_ready(tmp_path: Path) -> None:
    config_path = _write_external_config(tmp_path)

    state = panel.load_local_financial_projection(
        ROOT,
        {
            panel.FEATURE_FLAG: "on",
            panel.FINANCIAL_CONFIG_ENV: str(config_path),
        },
    )

    assert state["status"] == "ready"
    assert state["financial_packet"]["external_action_performed"] is False
    assert state["compliance_packet"] is None


def test_explicit_empty_environment_does_not_inherit_ambient_flags(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv(panel.FEATURE_FLAG, "true")
    monkeypatch.setenv(panel.FINANCIAL_CONFIG_ENV, "/does/not/exist.json")

    state = panel.load_local_financial_projection(ROOT, {})

    assert state["status"] == "disabled"


def test_enabled_projection_rejects_noncanonical_project_root(
    tmp_path: Path,
) -> None:
    false_root = tmp_path / "repository"
    false_root.mkdir()

    with pytest.raises(panel.FinancialEvidencePanelError, match="canonical"):
        panel.load_local_financial_projection(
            false_root,
            {panel.FEATURE_FLAG: "true"},
        )


def test_financial_and_compliance_packets_require_exact_scope_link(
    tmp_path: Path,
) -> None:
    financial_config = _example_config()
    expected_financial = prepare_financial_evidence_packet(financial_config)
    financial_path = _write_private_json(
        tmp_path,
        "financial.json",
        financial_config,
    )
    compliance_path = _write_private_json(
        tmp_path,
        "compliance.json",
        _compliance_config(expected_financial["packet_id"]),
    )

    state = panel.load_local_financial_projection(
        ROOT,
        {
            panel.FEATURE_FLAG: "true",
            panel.FINANCIAL_CONFIG_ENV: str(financial_path),
            panel.COMPLIANCE_CONFIG_ENV: str(compliance_path),
        },
    )

    assert state["status"] == "ready"
    assert (
        state["compliance_packet"]["financial_evidence_packet_id"]
        == state["financial_packet"]["packet_id"]
    )


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("tenant_id", "TENANT-OTHER"),
        ("engagement_id", "ENGAGEMENT-OTHER"),
        ("as_of_date", "2026-07-29"),
        (
            "financial_evidence_packet_id",
            "AIGC-FIN-EVIDENCE-000000000000000000",
        ),
    ],
)
def test_cross_scope_compliance_packet_is_rejected(
    tmp_path: Path,
    field: str,
    value: str,
) -> None:
    financial_config = _example_config()
    financial_packet = prepare_financial_evidence_packet(financial_config)
    compliance = _compliance_config(financial_packet["packet_id"])
    compliance[field] = value
    financial_path = _write_private_json(
        tmp_path,
        "financial.json",
        financial_config,
    )
    compliance_path = _write_private_json(
        tmp_path,
        "compliance.json",
        compliance,
    )

    with pytest.raises(panel.FinancialEvidencePanelError, match="same scope"):
        panel.load_local_financial_projection(
            ROOT,
            {
                panel.FEATURE_FLAG: "true",
                panel.FINANCIAL_CONFIG_ENV: str(financial_path),
                panel.COMPLIANCE_CONFIG_ENV: str(compliance_path),
            },
        )


def test_ui_summaries_are_allowlisted_and_omit_private_identifiers_and_paths(
    tmp_path: Path,
) -> None:
    packet = prepare_financial_evidence_packet(_example_config())

    provider_rows = panel._safe_provider_summary(packet)
    project_rows = panel._safe_project_summary(packet)

    assert provider_rows
    assert project_rows
    assert all(
        set(row) == {"source_class", "count", "net_settled_cash"}
        for row in provider_rows
    )
    assert all(
        set(row)
        == {
            "project",
            "evidence_state",
            "documented_hours",
            "selected_planning_value",
            "status",
        }
        for row in project_rows
    )

    serialized = json.dumps(
        {"providers": provider_rows, "projects": project_rows},
        sort_keys=True,
    )
    for record in packet["records"]:
        assert record["record_id"] not in serialized
        assert record["source_ref_id"] not in serialized
    assert str(tmp_path) not in serialized
    assert os.sep + "private-evidence" + os.sep not in serialized


def test_panel_source_has_no_download_or_export_surface() -> None:
    source = Path(panel.__file__).read_text(encoding="utf-8")

    prohibited_api_names = {
        "download_button",
        "file_uploader",
        "data_editor",
    }
    assert all(name not in source for name in prohibited_api_names)
    assert "st.json(" not in source
    assert "st.code(" not in source


def test_operator_cockpit_wires_the_financial_evidence_tab() -> None:
    source = (
        ROOT / "src" / "dashboard" / "operator_cockpit_app.py"
    ).read_text(encoding="utf-8")

    assert '"Financial Evidence"' in source
    assert "render_financial_evidence_tab(st, root)" in source
