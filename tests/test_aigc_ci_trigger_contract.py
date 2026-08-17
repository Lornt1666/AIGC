from __future__ import annotations

from pathlib import Path

import yaml


ROOT = Path(__file__).resolve().parents[1]
WORKFLOW = ROOT / ".github" / "workflows" / "aigc-ci.yml"


def test_aigc_ci_admits_main_and_release_pull_requests_and_manual_dispatch() -> None:
    workflow = yaml.load(WORKFLOW.read_text(encoding="utf-8"), Loader=yaml.BaseLoader)
    triggers = workflow["on"]
    assert "workflow_dispatch" in triggers
    assert triggers["push"]["branches"] == ["**"]
    assert triggers["pull_request"]["branches"] == ["main", "release/**"]


def test_aigc_ci_retains_exact_requested_revision_identity_gate() -> None:
    text = WORKFLOW.read_text(encoding="utf-8")
    assert "REQUESTED_REVISION:" in text
    assert "Checkout exact requested revision" in text
    assert "Verify exact requested checkout" in text
    assert 'observed_head_sha="$REQUESTED_REVISION"' not in text
    assert 'observed_head_sha="$(git rev-parse HEAD)"' in text


def test_aigc_ci_only_invokes_repository_scripts_that_exist() -> None:
    text = WORKFLOW.read_text(encoding="utf-8")
    canonical_runner = "scripts/run_exact_sha_ci_contract.py"
    canonical_contract = "config/exact_sha_ci_validation_contract.json"
    assert (ROOT / canonical_runner).is_file()
    assert (ROOT / canonical_contract).is_file()
    assert canonical_runner in text
    assert canonical_contract in text
    for script in (
        "scripts/validate_aigc_mcp_loopback_v2.py",
        "scripts/validate_aigc_universal_integration.py",
        "scripts/build_aigc_system_atlas_data.py",
        "scripts/build_aigc_evidence_program.py",
    ):
        assert (ROOT / script).is_file()
        assert script in text
