# AIGC Devpost Gemini Workflow

## Evidence boundary

This implementation adds an end-to-end application path for a governed Gemini
assessment. Repository code and offline tests do not prove that Gemini, Google
Cloud, customers, revenue, or production operation exists. A production claim
requires an authorized deployment and retained runtime receipts.

## Workflow

1. Cloud Run IAM authenticates access to the private service. The application
   then issues a signed, HTTP-only operator session after a separate
   command-token check, so the app does not reuse Cloud Run's `Authorization`
   header.
2. An authenticated operator submits a permitted opportunity. URL credentials
   and recognized credential patterns—including incomplete private-key
   blocks—fail closed; common contact data is redacted, and only the
   credential-free source origin is sent or stored. Pattern detection is a
   defense-in-depth control, not a guarantee that arbitrary secrets can be
   identified.
3. The application writes a `workflow_started` audit event before attempting a
   provider call. If this write fails, Gemini is not called.
4. The deployed application calls Gemini through Vertex AI using its Cloud Run
   service identity and Application Default Credentials. No API key is stored.
5. Gemini returns a Pydantic-constrained assessment with pointers to the exact
   supplied fields used as evidence.
6. Deterministic policy validates those pointers and evaluates AI permission,
   disclosure, injection signals, risk, score, and the mandatory human-review
   flag.
7. The application records a create-only success or failure event with an
   integrity hash and explicit call status: not attempted, confirmed, or
   attempted with outcome unknown.
8. The authenticated operator records exactly one approve, deny, or revise
   attestation. Approval is available only after the deterministic policy
   permits an internal draft; deny/revise remain available for policy findings.
9. Approval authorizes internal use only. It never performs an external
   business action.

## Required environment

| Variable | Requirement |
|---|---|
| `AIGC_COMMAND_CENTER_TOKEN` | Secret Manager reference used by the existing operator boundary |
| `AIGC_OPERATOR_SUBJECT_KEY` | Separate Secret Manager pepper used for domain-separated HMAC operator identifiers; required in production |
| `AIGC_RELEASE_REVISION` | Exact 40-character Git SHA embedded in runtime evidence |
| `AIGC_GEMINI_ENABLED` | Must be exactly enabled only after deployment approval |
| `GOOGLE_CLOUD_PROJECT` | Exact Google Cloud project ID |
| `GOOGLE_CLOUD_LOCATION` | Approved Vertex AI location compatible with the selected model |
| `AIGC_GEMINI_MODEL` | Exact deployed Gemini model name; no silent default |
| `AIGC_GEMINI_EVIDENCE_BACKEND` | `gcs` in production |
| `AIGC_GEMINI_EVIDENCE_BUCKET` | Dedicated evidence bucket |
| `AIGC_GEMINI_EVIDENCE_PREFIX` | Defaults to `product-evidence/gemini` |
| `AIGC_GEMINI_TIMEOUT_SECONDS` | Hard SDK request timeout; defaults to `30` |
| `AIGC_GEMINI_MAX_OUTPUT_TOKENS` | Bounded output budget; defaults to `1200` |
| `AIGC_GEMINI_MAX_ATTEMPTS` | Total attempts, including the first; maximum `3` |
| `AIGC_ENV` | `production` on Cloud Run |
| `K_REVISION` | Cloud Run-provided runtime revision; required in production |

Production refuses the JSONL evidence backend because Cloud Run's writable
filesystem is ephemeral.

## Service identity

Use a dedicated Cloud Run service account. Grant only the minimum Vertex AI
prediction permission and bucket-scoped permissions needed to create, list, and
read evidence objects. Do not create or commit a service-account key file.

The deployment script deliberately requires the project, service account,
regions, model, evidence bucket, Artifact Registry repository, exact Git
revision, pinned secret versions, and an exact-target deployment permit as
operator inputs. Before any Git or Google Cloud command, it also requires the
accepted environment decision and deployment baseline to authorize production
resource creation, apply, and deployment. Both currently deny those actions, so
the script fails closed. The committed permit is an expired, unauthorized
example and cannot enable deployment.

After those separately governed files are approved, the script tags the build
with the authorized revision, resolves the registry digest, and deploys the
digest rather than a mutable tag. Before building, it verifies that the exact
revision is checked out, that the tracked and untracked working tree is clean,
that the target region matches the accepted primary region, and that every
native Git/Google Cloud command succeeds. The registry repository, evidence
bucket, service account, IAM bindings, and secret versions must already exist
and must be reviewed before use. Running the script is an external action and
requires explicit authorization.

The container runs as an unprivileged `aigc` user. The deploy command bounds
instances, concurrency, request timeout, and port from the accepted baseline;
those values are policy inputs, not proof of load capacity.

## API

- `GET /api/session`
- `POST /api/session`
- `POST /api/session/logout`
- `GET /api/gemini/status`
- `POST /api/gemini/workflows`
- `GET /api/gemini/workflows/{run_id}`
- `POST /api/gemini/workflows/{run_id}/decision`

Gemini routes require either the signed operator-session cookie or the
application-specific `X-AIGC-Command-Token` header. In production,
`Authorization` is reserved for Cloud Run IAM. Basic/Bearer application-token
fallback exists only in non-production local development.

Example intake:

```json
{
  "title": "Permissioned opportunity",
  "description": "A real description with customer-private details removed.",
  "source_url": "https://example.com/opportunity",
  "constraints": ["No external business action", "Human review required"],
  "ai_assistance_permitted": true,
  "ai_disclosure_required": true
}
```

## Validation

```bash
python -m pytest tests/test_gemini_workflow.py tests/test_cloud_webapp.py
python scripts/run_gemini_workflow_smoke.py
```

The smoke script uses an explicit offline stub and writes a summary stating
separately that no model API call, deployment, or external business action
occurred. It records three events: workflow start, structured result, and
operator attestation.

## Production acceptance evidence

Do not update Devpost capability claims until all of the following are captured:

- successful Cloud Run revision and immutable image digest;
- exact Vertex AI model and region;
- successful live execution event with
  `model_api_call_performed: true` and `live_model_call: true`;
- model usage and latency metadata;
- deterministic policy result;
- operator attestation bound to the assessment hash and release revision;
- durable Cloud Storage evidence object identifiers;
- redacted screenshot or dashboard view;
- exact Git revision and passing CI;
- customer consent where a real customer input is used.

## Critical activation blockers

The repository intentionally does not represent these as completed:

- an authorized Google Cloud staging/production environment and runtime
  receipts;
- a Gemini-aware durable emergency stop checked before and after the provider
  call;
- a judge-safe, read-only identity role or independently hosted redacted demo;
- durable idempotency, per-operator rate limits, and evidenced cloud budget or
  quota enforcement;
- a dedicated Gemini-only production surface or remediation of the legacy
  command-center endpoints that share the current app;
- an explicit production image allowlist that excludes internal repository data;
- a readiness probe that verifies required runtime dependencies without
  presenting liveness as operational proof;
- Cloud Storage handoff receipts containing object URI and generation;
- the accepted load-balancer, Cloud Armor, identity-provider, and Secret Broker
  chain required by the canonical production baseline.

Until these are resolved and the acceptance evidence above exists, keep the PR
draft and describe the feature as an implemented, offline-validated workflow,
not as production-deployed or competition-submitted.

The shared-token session proves possession of the operator credential and
records a domain-separated HMAC subject identifier using a dedicated production
pepper. The raw label and pepper are not written to workflow evidence. This
does not independently prove that the actor was human. Do not describe the event
as verified human identity without a separately evidenced identity provider and
trusted principal.

Model evidence pointers prove only that the cited input field existed. The
input itself is operator-supplied and not externally verified; structured
output does not prove the truth of the source material.

The generation-time `if_generation_match=0` precondition prevents accidental
overwrite of an existing event object. A production claim of retention,
tamper-resistance, or regulatory immutability additionally requires reviewed
bucket IAM, retention-policy, and audit-log evidence.
