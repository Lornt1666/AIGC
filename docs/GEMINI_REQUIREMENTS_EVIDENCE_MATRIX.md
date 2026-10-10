# Gemini Requirements-to-Evidence Matrix

## Interpretation

“Implemented” below means that the repository contains the named code or
configuration contract. “Test-covered” means a repository test exercises that
contract. Neither status proves that the exact PR head passed hosted CI or that
Google Cloud executed it. Runtime and publication claims remain incomplete
until their external receipts exist.

| Requirement | Repository evidence | Test or validation evidence | Claim currently supported | External receipt required |
|---|---|---|---|---|
| RegenExcalibur business identity and repository scope | `config/gemini_staging_authorization.example.json`; `config/gemini_runtime_receipt.example.json` | Staging validator fixes the repository and identity fields | The workflow is prepared for `Lornt1666/AIGC` under RegenExcalibur | Authorized staging and runtime receipts |
| Structured Gemini assessment | `src/gemini_workflow/provider.py`; `models.py`; `service.py` | `tests/test_gemini_workflow.py` | The repository implements a Vertex AI Gemini adapter and strict assessment contract | Live runtime receipt before claiming a model call |
| Deterministic policy and human review | `policy.py`; `service.py`; `models.py` | `tests/test_gemini_workflow.py`; `tests/test_gemini_surfaces.py` | Output is policy-evaluated and one operator decision is required for internal use | Generation-bound execution and decision receipts for a specific live run |
| No external business action | `WorkflowRecord` uses false-only external-action fields; service decision records internal-use-only approval | Workflow and surface tests | The implemented Gemini path has no route that performs an external business action | Runtime receipt for a specific run |
| Durable Gemini emergency stop | `control_store.py`; `migrations/002_gemini_runtime_controls.sql`; stop and admin-clear API routes | `tests/test_gemini_controls.py`; `tests/test_gemini_surfaces.py` | A durable stop-epoch contract is implemented and fail-closed | Passing exact-head CI and staging control-store readiness |
| Idempotency, rate, and reserved-token limits | `control_store.py`; `runtime_limits.py`; `config/gemini_runtime_limits.json` | `tests/test_gemini_controls.py`; `tests/test_gemini_image_allowlist.py` | Stable-principal idempotency and bounded application limits are implemented | Passing exact-head CI; runtime receipt for enforcement in the authorized staging revision |
| Cloud spending guardrails | `gemini_staging_authorization.example.json` records CAD ceiling, budget acknowledgement, quotas and app-limit review | `tests/test_gemini_staging_authorization.py` | The authorization contract requires reviewed spend controls and states that budgets are alerts, not hard caps | Owner-approved ceiling plus inspected Billing budget/quota configuration |
| Isolated Gemini-only production surface | `src/webapp/gemini_app.py`; `Dockerfile.gemini`; deployment helper sets explicit operator or judge surface | `tests/test_gemini_surfaces.py`; `tests/test_gemini_image_allowlist.py` | Separate operator and judge route sets are implemented; legacy routes are excluded | Deployment receipt and inspected Cloud Run revisions |
| Judge-safe read-only access | Judge surface initializes neither provider nor control writer; `judge_receipts.py`; `judge_store.py`; `scripts/publish_gemini_judge_receipt.py` | `tests/test_gemini_surfaces.py`; `tests/test_judge_receipts.py`; `tests/test_judge_store.py`; `tests/test_publish_gemini_judge_receipt.py` | A provider-free, read-only, sanitized receipt surface and default-local/create-only publication command are implemented | Explicit judge-publication authorization, GCS publication receipt and access check |
| Container file allowlist | `Dockerfile.gemini`; `.gcloudignore.gemini`; `cloudbuild.gemini.yaml` | `tests/test_gemini_image_allowlist.py` | The Gemini image build context is default-deny, exact-file allowlisted and non-root | Cloud Build receipt and immutable Artifact Registry digest |
| Real readiness checks | `readiness.py`; `/healthz`; `/readyz`; runtime limits list required probes | `tests/test_gemini_readiness.py` | Readiness covers configuration, governed secrets, exact-sentinel GCS metadata (without bucket listing), durable controls and Vertex model metadata without generation | `200` readiness receipt from each candidate revision |
| Governed secrets | `secret_broker.py`; `config/gemini_secret_access_manifest.json` | `tests/test_secret_broker.py`; staging authorization tests | Exact numeric Secret Manager references flow through Omega-X → Ultra-Secrets → Secret Broker; audit receipts are metadata-only | Exact-version resource inspection, IAM review and readiness receipt |
| GCS URI/generation evidence | `evidence.py`; durable completion stores the event ID, object URI and generation | `tests/test_gcs_evidence_receipts.py`; control and workflow tests | Create-only, generation-bound evidence and exact-receipt reads are implemented | Live object URI, exact generation and record hash |
| Orphan-evidence quarantine | `service.py` exposes execution/decision records only after exact durable completion bindings | `tests/test_gemini_receipt_binding.py`; control and workflow tests | Unbound execution or decision objects are not treated as completed workflow evidence | Staging failure-injection receipt if this behavior is claimed operationally |
| Immutable Canadian staging deployment | Authorization validator permits recorded Canadian regions; deploy helper resolves a digest and deploys no-traffic candidates | `tests/test_gemini_staging_authorization.py`; `tests/test_gemini_staging_deploy.py` | A default-deny, permit-bound deployment procedure is implemented | Approved configuration, Cloud Build ID, digest and both Cloud Run revisions |
| Exactly one controlled live assessment | `scripts/run_controlled_gemini_canary.py`; `config/gemini_canary_intake.example.json`; one-call permit template | `tests/test_controlled_gemini_canary.py` | A permit-bound, no-automatic-retry synthetic canary procedure is implemented | Completed live permit and `aigc.gemini-runtime-receipt.v1` |
| Passing CI receipt | `.github/workflows/aigc-ci.yml`; CI receipt template | Canary validation rejects zero-step jobs and missing artifact families | The workflow definition and receipt contract exist | Hosted Actions run with allocated steps, logs, success, exact head SHA and required artifacts |
| Redacted judge walkthrough | `config/gemini_judge_media_manifest.example.json`; capture procedure in the completion runbook | Manual hash and redaction review | A default-deny capture manifest is prepared | Reviewed video/screenshots, file hashes and explicit publication authorization |
| PR merge and Devpost submission | Completion runbook and this matrix define receipt gates | Manual accountable review | A responsible completion procedure is documented | PR approval/merge commit and Devpost preview/submission confirmation |

## Critical missing external assets

Only these external assets remain necessary to move from repository
implementation to a receipt-backed competition submission:

1. A passing GitHub Actions receipt for the exact release SHA with allocated
   steps, complete logs, and the required artifact families.
2. An unexpired, explicitly approved Canadian staging authorization plus
   inspected project, IAM, service accounts, exact secret versions, evidence
   buckets, Billing budget, quotas, and CAD ceiling.
3. A staging deployment receipt containing the Cloud Build ID, immutable image
   digest, and no-traffic operator and judge Cloud Run revisions.
4. One completed permit-bound runtime receipt for the synthetic fixture,
   including model, location, latency, provider-reported usage, Git SHA, image
   digest, Cloud Run revision, and generation-bound evidence.
5. One explicitly authorized sanitized judge-publication receipt and a
   redaction-reviewed media manifest with hashes for the walkthrough and
   screenshots.
6. PR approval, required-check success, and the merge commit SHA.
7. A reviewed Devpost preview, claim-to-receipt check, and final submission
   confirmation.
