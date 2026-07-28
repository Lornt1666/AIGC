# Procurement Checklist for Gemini-governed Opportunity Workflow

This checklist collects the exact artifacts and validation commands required to complete a governed Gemini staging deployment and produce the receipts needed for Devpost/XPRIZE claims. **Do NOT commit any filled authorization, secret manifests, or numeric secret versions to the repository.** Store completed artifacts in a secure out-of-repo location and record path/URIs in your deployment receipts.

## Quick summary
- Release SHA: `git rev-parse HEAD` at time of artifact creation.
- All validation scripts live in `scripts/` and example templates live in `config/` (look for files named `*.example.json`).

## Required artifacts and acceptance checks

1) CI Receipt (Hosted GitHub Actions)
- Files referenced: `.github/workflows/aigc-ci.yml` and `config/gemini_ci_receipt.example.json`
- Acceptance: Hosted Actions run for head SHA with conclusion `success`, steps_executed > 0, and artifacts uploaded: `gemini-workflow-offline-smoke`, `test-results`, `terraform-validation` (or equivalents).
- Validate command: Inspect Actions run URL or use the action's uploaded artifact listing.

2) Staging Authorization (out-of-repo JSON)
- Template: `config/gemini_staging_authorization.example.json`
- Must include: project_id, primary_region, vertex_location, artifact_registry_repository, cloud_sql_instance_connection_name, database_name, evidence_bucket, judge_receipt_bucket, operator_service_name, judge_service_name, service account emails, and explicit Secret Manager numeric versions.
- Validate with: `python scripts/validate_gemini_staging_authorization.py authorization.json --summary`

3) Secret Manifest (out-of-repo)
- Template: `config/gemini_secret_access_manifest.example.json`
- Each secret ref must be numeric versioned: `projects/.../secrets/.../versions/N`
- Validate: ensure no `latest` references; run secret validation script (if present) or `python -c "import json; print('ok' if all('/versions/' in v for v in json.load(open('manifest.json')).values()) else 'bad')"`

4) Immutable Build Artifact
- Triggered by: `cloudbuild.gemini.yaml` (or `scripts/deploy_gemini_staging.py` build step)
- Acceptance: artifact registry image digest (sha256:...) recorded in deployment receipt.
- Validate: `gcloud artifacts docker images describe <IMAGE_TAG> --format='value(image_summary.digest)'`

5) Cloud Run No-Traffic Candidate Revisions
- Acceptance: deployment output contains `operator_revision`, `judge_revision`, candidate URLs, and image-digest binding.
- Validate: `gcloud run services describe <service> --format=json`

6) Live Assessment Permit (one-run permit)
- Template: `config/gemini_live_assessment_permit.example.json`
- Fields locked: release_revision, image_digest, cloud_run_revision, input_fixture_sha256, maximum_model_calls == 1
- Validate: `python scripts/validate_live_permit.py live_permit.json` (or `scripts/run_controlled_gemini_canary.py --validate-permit`)

7) Canonical Input Fixture SHA256
- Template fixture: `config/gemini_canary_intake.example.json`
- Canonical serialization: `json.dumps(obj, sort_keys=True, separators=(',',':'), ensure_ascii=False)` then sha256
- Compute with: `python - <<'PY'
import json,hashlib
j=json.load(open('config/gemini_canary_intake.example.json',encoding='utf8'))
s=json.dumps(j,sort_keys=True,separators=(',',':'),ensure_ascii=False).encode('utf8')
print(hashlib.sha256(s).hexdigest())
PY`

8) Controlled Canary Runtime Receipt
- Produced by: `scripts/run_controlled_gemini_canary.py` after permit and candidate deployment
- Acceptance: JSON receipt with model, location, latency_ms, usage metadata, input_sha256, evidence.object_uri (gs://...), and evidence.generation number.
- Validate: receipt ties to release SHA and image digest.

9) Judge Receipt Publication
- Script: `scripts/publish_gemini_judge_receipt.py`
- Acceptance: judge receipt JSON written to `judge_receipt_bucket` with generation; publication receipt produced locally.
- Validate: GCS object exists and `gsutil stat gs://...` shows generation and size.

10) Media / Walkthrough Manifest (redacted)
- Template: `config/gemini_judge_media_manifest.example.json`
- Acceptance: redaction_review true, reviewed_by and reviewed_at populated, media hashes recorded.

11) Devpost / PR Claim Conditions
- Merge PR only after required receipts exist and are embedded or linked in the PR.
- Devpost claim paragraph: update with exact runtime receipt fields (do not infer values).

## Useful commands
- Release SHA: `git rev-parse HEAD`
- Canonical input sha: see snippet above
- Artifact digest: `gcloud artifacts docker images describe <TAG> --format='value(image_summary.digest')`
- Cloud Run describe: `gcloud run services describe <service> --region <region> --format=json`
- Check GCS object generation: `gsutil stat gs://bucket/object`

## Validation scripts (where to look)
- `scripts/validate_gemini_staging_authorization.py`
- `scripts/validate_live_permit.py` or the canary script's validation mode
- `scripts/run_controlled_gemini_canary.py` (computes canonical input sha and emits runtime receipt)
- `scripts/deploy_gemini_staging.py` (produces deployment plan and receipts)

## Notes & warnings
- NEVER commit filled authorization or numeric secret version files. Keep them in a secure store (Secret Manager, Vault, or an internal secure drive) and reference them by path/URI in your deployment receipts.
- Keep `AIGC_GEMINI_ENABLED=false` as default in CI and dev environments. Only flip for controlled staging runs after permit checks pass.

---
Generated by repository assistant: create docs/PROCUREMENT_CHECKLIST.md to map required artifacts to repo files and validation commands.
