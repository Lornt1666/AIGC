from __future__ import annotations

from pathlib import Path

import pytest

from scripts.verify_nexus_supply_chain import SupplyChainError, verify


ROOT = Path(__file__).resolve().parents[1]


def test_repository_supply_chain_contract_is_fail_closed() -> None:
    receipt = verify(ROOT)
    assert receipt["locked_package_count"] > 0
    assert receipt["all_dependencies_hashed"] is True
    assert receipt["build_inputs_allowlisted"] is True
    assert receipt["external_action_performed"] is False


def test_missing_dependency_hash_is_rejected(tmp_path: Path) -> None:
    for relative in (
        "Dockerfile.nexus",
        "cloudbuild.nexus.yaml",
        "config/nexus_build_context_allowlist.json",
    ):
        target = tmp_path / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes((ROOT / relative).read_bytes())
    (tmp_path / "requirements.lock").write_text(
        "example==1.2.3\n", encoding="utf-8"
    )
    with pytest.raises(SupplyChainError, match="hash is missing"):
        verify(tmp_path)


def test_ci_build_and_runtime_smoke_preserve_supply_chain_boundary() -> None:
    workflow = (ROOT / ".github/workflows/aigc-ci.yml").read_text(
        encoding="utf-8"
    )
    assert "scripts/prepare_nexus_build_context.py" in workflow
    assert 'docker build --file Dockerfile.nexus --tag "$image_tag" .' not in workflow
    assert '--build-arg "RELEASE_SHA=$REQUESTED_REVISION"' in workflow
    assert '--build-arg "SOURCE_CONTEXT_SHA256=$context_digest"' in workflow
    assert '"$context_dir"' in workflow
    assert "--read-only" in workflow
    assert "--network none" in workflow
    assert "--cap-drop ALL" in workflow
    assert "--security-opt no-new-privileges:true" in workflow
    assert '"release_base_image_status": "immutable_default_verified"' in workflow
    assert '"python_base_image": os.environ["NEXUS_CI_BASE_IMAGE"]' in workflow
    assert '"registry_push_performed": False' in workflow
    assert '"deployment_performed": False' in workflow
