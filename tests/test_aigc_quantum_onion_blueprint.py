from __future__ import annotations

import json
from pathlib import Path

from src.core.contract_validator import validate_file


def test_tailored_quantum_onion_blueprint_is_schema_valid() -> None:
    path = Path("config/aigc_quantum_onion_defense_blueprint.json")
    payload = json.loads(path.read_text(encoding="utf-8"))

    assert payload["scope"] == "Lornt1666/AIGC"
    assert payload["external_action_default"] == "blocked_until_operator_proceeds"
    assert payload["authorized_disclosure_boundary"]["backdoor_access_allowed"] is False
    assert payload["authorized_disclosure_boundary"]["evidence_export_allowed"] is True
    assert len(payload["layers"]) == 5
    assert {layer["layer_id"] for layer in payload["layers"]} == {
        "aegis_shield",
        "excalibur_seals",
        "quantum_maze",
        "medusa_chamber",
        "ananta_core",
    }
    validate_file("aigc_quantum_onion_defense_blueprint", path)


def test_tailored_quantum_onion_blueprint_doc_exists_and_is_specific() -> None:
    doc = Path("docs/AIGC_QUANTUM_ONION_TAILORED_DEFENSE_BLUEPRINT.md")
    text = doc.read_text(encoding="utf-8")

    assert "Lornt1666/AIGC" in text
    assert "Aegis Shield" in text
    assert "Excalibur Seals" in text
    assert "Quantum Maze" in text
    assert "Medusa Chamber" in text
    assert "Ananta Core" in text
    assert "not a backdoor" in text
