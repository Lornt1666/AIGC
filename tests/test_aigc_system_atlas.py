from __future__ import annotations

from pathlib import Path

from scripts.build_aigc_system_atlas_data import build_atlas_data


ROOT = Path(__file__).resolve().parents[1]


def test_atlas_snapshot_is_derived_from_canonical_sources() -> None:
    snapshot = build_atlas_data()
    assert snapshot["identity"]["name"] == (
        "Artificial Intelligence Gladiator Coliseum (AIGC)"
    )
    assert snapshot["portfolio"] == {
        "integrated_subsystems": 5,
        "delivery_surfaces": 8,
        "connectors": 5,
        "occupation_packs": 13,
        "wealth_actions": 16,
        "mcp_tools": 11,
        "life_domains": 7,
        "regenexcalibur_agent_roles": 8,
        "llm_training_cost_cad": 0,
        "llm_gpu_hours": 0,
    }
    assert snapshot["readiness"]["verified_required_checks"] == 12
    assert snapshot["readiness"]["unverified_required_checks"] == 22
    assert snapshot["readiness"]["verified_applicable_ratio"] == 0.352941
    assert snapshot["readiness"]["production_ready"] is False
    assert len(snapshot["snapshot_sha256"]) == 64


def test_atlas_document_defines_every_named_subsystem_and_parameter() -> None:
    snapshot = build_atlas_data()
    atlas = (ROOT / "docs" / "architecture" / "AIGC_SYSTEM_ATLAS_V1.md").read_text(
        encoding="utf-8"
    )
    for subsystem in snapshot["subsystems"]:
        assert subsystem["name"] in atlas
    for parameter in snapshot["parameters"]:
        assert parameter["symbol"] in atlas
    assert atlas.count("```mermaid") >= 5
    assert "35.2941%" in atlas
    assert "12 / 34" in atlas


def test_root_readme_has_one_canonical_name_and_routes_to_visual_atlas() -> None:
    readme = (ROOT / "README.md").read_text(encoding="utf-8")
    agents = (ROOT / "AGENTS.md").read_text(encoding="utf-8")
    assert "Artificial Intelligence Gladiator Coliseum" in readme
    assert "Artificial Intelligence Gladiator Coliseum" in agents
    assert "Gladiator Colosseum" not in agents
    assert "AIGC_SYSTEM_ATLAS_V1.md" in readme
    assert "AIGC_SYSTEM_ATLAS_V1.pptx" in readme


def test_presentation_is_a_nonempty_powerpoint_package() -> None:
    presentation = (
        ROOT / "docs" / "presentations" / "AIGC_SYSTEM_ATLAS_V1.pptx"
    )
    assert presentation.is_file()
    assert presentation.stat().st_size > 50_000
    assert presentation.read_bytes()[:2] == b"PK"
