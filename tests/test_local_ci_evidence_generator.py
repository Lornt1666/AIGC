from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "generate-evidence.sh"
VERIFIER = ROOT / "scripts" / "verify_evidence_manifest.py"


def test_local_evidence_generator_uses_canonical_repository_paths() -> None:
    text = SCRIPT.read_text(encoding="utf-8")

    assert "scripts/run_provider_discovery_mock.py" in text
    assert 'TERRAFORM_ROOT="infra/terraform/gcp"' in text
    assert "python -m pytest" in text
    assert "python src/aigc.py readiness" in text
    assert '--artifact-root "$OUTPUT_ROOT/production_readiness"' in text

    assert "python -m app.simulation" not in text
    assert "python -m app.readiness" not in text
    assert "terraform/staging" not in text


def test_local_evidence_generator_fails_closed_without_fabricated_reports() -> None:
    text = SCRIPT.read_text(encoding="utf-8")

    assert "set -Eeuo pipefail" in text
    assert "git status --porcelain=v1 --untracked-files=all" in text
    assert "git rev-parse HEAD" in text
    assert "git diff --quiet" in text
    assert "git diff --cached --quiet" in text
    assert "git ls-files --others --exclude-standard" in text
    assert "FAILED_CLOSED" in text
    assert '"hosted_ci_replacement": False' in text
    assert '"provider_action_performed": False' in text
    assert '"terraform_apply_performed": False' in text
    assert '"external_action_performed": False' in text

    assert "|| true" not in text
    assert "status\":\"simulated" not in text
    assert "partial evidence generated" not in text
    assert "structural_score\": 74.5" not in text
    assert "terraform apply" not in text


def test_local_evidence_generator_binds_expected_pr_head() -> None:
    text = SCRIPT.read_text(encoding="utf-8")

    assert 'EXPECTED_REVISION="${AIGC_EXPECTED_REVISION:-}"' in text
    assert 'EXPECTED_PR_NUMBER="${AIGC_EXPECTED_PR_NUMBER:-}"' in text
    assert "Current revision does not match AIGC_EXPECTED_REVISION" in text
    assert "AIGC_EXPECTED_PR_NUMBER must be a positive integer" in text
    assert '"contract_id": "AIGC-LOCAL-CI-REPOSITORY-STATE-001"' in text
    assert '"expected_pr_assertion_source": "operator_environment"' in text
    assert '"worktree_clean": True' in text
    assert '"index_clean": True' in text
    assert '"tracked_diff_clean": True' in text
    assert '"untracked_clean": True' in text


def test_local_evidence_generator_asserts_inert_terraform_plan() -> None:
    text = SCRIPT.read_text(encoding="utf-8")

    assert "-refresh=false" in text
    assert "staging.tfvars.example" in text
    assert 'changes = plan.get("resource_changes") or []' in text
    assert "Inert Terraform plan unexpectedly contains resource changes" in text
    assert '"resource_change_count": 0' in text


def test_local_evidence_generator_hashes_and_verifies_bundle_artifacts() -> None:
    text = SCRIPT.read_text(encoding="utf-8")
    verifier = VERIFIER.read_text(encoding="utf-8")

    assert '"contract_id": "AIGC-LOCAL-CI-EVIDENCE-MANIFEST-001"' in text
    assert "sha256(path.read_bytes()).hexdigest()" in text
    assert '"artifact_count": len(entries)' in text
    assert 'root / "evidence-manifest.json"' in text
    assert "python scripts/verify_evidence_manifest.py" in text
    assert 'VERIFICATION_RECEIPT="${OUTPUT_ROOT}.verification.json"' in text
    assert 'VERIFICATION_LOG="${OUTPUT_ROOT}.verification.log"' in text
    assert 'tee "$OUTPUT_ROOT/logs/manifest-verification.log"' not in text

    assert "Manifest file-set mismatch" in verifier
    assert "Digest mismatch" in verifier
    assert "Symlinks are prohibited" in verifier
    assert "Canonical production-readiness JSON evidence is missing" in verifier
