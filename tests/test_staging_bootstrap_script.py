from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "bootstrap-staging.sh"


def test_staging_bootstrap_is_mock_only_and_revision_bound() -> None:
    text = SCRIPT.read_text(encoding="utf-8")

    assert "git rev-parse HEAD" in text
    assert "scripts/run_provider_discovery_mock.py" in text
    assert "--repository-revision" in text
    assert 'echo "Mode: MOCK_ONLY"' in text
    assert "evaluate_staging_procurement" in text
    assert '"next_gate": "PROVIDER_DISCOVERY_AUTHORIZATION"' in text


def test_staging_bootstrap_does_not_fabricate_receipts_or_apply() -> None:
    text = SCRIPT.read_text(encoding="utf-8")

    forbidden = (
        "STAGING_TARGET_SPECIFIED",
        "STATE_BACKEND_BOOTSTRAPPED",
        "STAGING_BOOTSTRAP_COMPLETE",
        "python -m app.discovery",
        "python -m app.readiness",
        "terraform apply",
        ".readiness/",
    )
    for marker in forbidden:
        assert marker not in text


def test_staging_bootstrap_states_external_action_boundary() -> None:
    text = SCRIPT.read_text(encoding="utf-8")

    assert "No provider read, Terraform apply, identity configuration" in text
    assert "secret access, resource creation, or external action occurred" in text
