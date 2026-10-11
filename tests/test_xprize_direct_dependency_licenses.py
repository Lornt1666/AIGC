from __future__ import annotations

import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
REQUIREMENTS = ROOT / "requirements-gemini.txt"
LICENSES = ROOT / "config" / "xprize_direct_dependency_licenses.json"


def test_every_direct_gemini_requirement_has_verified_license_evidence():
    requirements = tuple(
        line.strip()
        for line in REQUIREMENTS.read_text(encoding="utf-8").splitlines()
        if line.strip() and not line.lstrip().startswith("#")
    )
    payload = json.loads(LICENSES.read_text(encoding="utf-8"))
    assert payload["schema_version"] == "aigc.xprize-direct-dependency-licenses.v1"
    assert payload["requirements_file"] == "requirements-gemini.txt"

    dependencies = payload["dependencies"]
    mapped = tuple(item["requirement"] for item in dependencies)
    assert mapped == requirements
    assert len(mapped) == len(set(mapped))

    allowed = {
        "VERIFIED_UPSTREAM",
        "VERIFIED_PYPI_METADATA",
        "VERIFIED_UPSTREAM_AND_PYPI_METADATA",
        "VERIFIED_UPSTREAM_AND_PYPI_BINARY_METADATA",
    }
    for item in dependencies:
        assert item["license_spdx"] not in {"", "UNKNOWN", "UNVERIFIED"}
        assert item["license_status"] in allowed
        assert item["source"]

    assert payload["direct_dependency_inventory_complete"] is True


def test_direct_license_inventory_does_not_overclaim_transitive_or_terms_review():
    payload = json.loads(LICENSES.read_text(encoding="utf-8"))
    assert payload["transitive_dependency_inventory_complete"] is False
    assert payload["provider_terms_review_complete"] is False
    assert payload["redistribution_notice_bundle_complete"] is False
    assert payload["legal_certification"] is False
