# AIGC Devpost Gemini Workflow

## Evidence boundary

This implementation adds an end-to-end application path for a governed Gemini
assessment. Repository code and offline tests do not prove that Gemini, Google
Cloud, customers, revenue, or production operation exists. A production claim
requires an authorized deployment and retained runtime receipts.

## Workflow

1. Cloud Run IAM authenticates access to the private service. The application
   separately authenticates the operator, runtime-administrator, or judge role
   with an application-specific header. It does not reuse Cloud Run's
   `Authorization` header.
2. An authenticated operator submits a permitted opportunity. URL credentials
   and recognized credential patterns—including incomplete private-key
   blocks—fail closed; common contact data is redacted, and only the
   credential-free source origin is sent or stored. Pattern detection is a
   defense-in-depth control, not a guarantee that arbitrary secrets can be
   identified.
3. The application reserves the stable principal, idempotency key, request
   hash, stop epoch, rate windows, and reserved-token budget in the durable
   control store. It then writes a `workflow_started` event. A control or start
   evidence failure prevents the provider call.
4. The deployed application calls Gemini through Vertex AI using its dedicated
   Cloud Run service identity and Application Default Credentials. Application
   secrets resolve only by exact Secret Manager version through Omega-X
   Orchestrator → Ultra-Secrets Agent → Secret Broker → Google Cloud Secret
   Manager. No model API key or service-account key file is stored.
5. Gemini returns a Pydantic-constrained assessment with pointers to the exact
   supplied fields used as evidence.
6. Deterministic policy validates those pointers and evaluates AI permission,
   disclosure, injection signals, risk, score, and the mandatory human-review
   flag.
7. The application records a create-only success or failure event with an
   integrity hash and explicit call status: not attempted, confirmed, or
   attempted with outcome unknown. A success is visible as completed only
   after the durable control record binds its exact event ID, `gs://` URI, and
   object generation.
8. The authenticated operator records exactly one approve, deny, or revise
   attestation. The decision has its own create-only evidence object and
   durable completion binding. Approval is available only after deterministic
   policy permits an internal draft; deny/revise remain available for policy
   findings.
9. Approval authorizes internal use only. It never performs an external
   business action.
10. A separate provider-free judge service can read only a prepublished,
    sanitized, generation-pinned receipt. Publication requires a byte-exact,
    content-bound human confirmation.

## Canonical operator workspace

The isolated `src.webapp.gemini_app` composition is the canonical Gemini
operator and judge surface for this slice. Its operator workspace now exposes
one complete browser flow over the existing governed API:

```text
transient operator credential
→ configuration/readiness/stop inspection
→ bounded opportunity intake
→ one idempotent assessment request
→ structured assessment and deterministic-policy review
→ one approve-internal-use | deny | revise attestation
→ runtime and decision receipt inspection
```

The browser does not store the operator or judge credential in a cookie,
`localStorage`, or `sessionStorage`. It clears the credential input after
copying it into page memory and clears page memory on disconnect. A longer-term
verified-identity-provider session remains preferable to a shared credential.

The UI renders untrusted assessment and receipt values through DOM
`textContent`, never HTML insertion. CSS and surface-specific JavaScript are
served through same-origin asset routes, so the application Content Security
Policy does not require `unsafe-inline` for scripts or styles. The judge asset
contains only its read-only receipt route and no Gemini provider, decision, or
runtime-control route.

Configuration and readiness remain visibly separate. A configured provider is
not displayed as ready unless the observed `/readyz` probe passes. A 502,
unknown network outcome, or uncertain provider result is displayed as
non-retriable; the UI never automatically repeats the assessment POST.

The API contract is additive and remains backward compatible. Assessment,
retrieval, and decision responses include:

- `api_contract_version`;
- a canonical `status_url`;
- a `controls` projection with server-admitted `allowed_decisions`;
- `approval_scope: internal_use_only`;
- `external_action_allowed: false`; and
- the applicable runtime or decision receipt.

This projection does not create a second workflow state, authority system, or
evidence store. Backend transition checks remain authoritative even if client
controls are modified.

## Required environment

| Variable | Requirement |
|---|---|
| `AIGC_SURFACE` | Explicitly `operator` or `judge`; production has no implicit default |
| `AIGC_RELEASE_REVISION` | Exact 40-character Git SHA embedded in runtime evidence |
| `AIGC_IMAGE_DIGEST` | Exact `sha256:` image digest; required in production |
| `AIGC_GEMINI_ENABLED` | Must be exactly enabled only after deployment approval |
| `GOOGLE_CLOUD_PROJECT` | Exact Google Cloud project ID |
| `GOOGLE_CLOUD_LOCATION` | `northamerica-northeast1` (Montréal), the currently listed Canadian regional Gemini endpoint; recheck the exact model before deployment |
| `AIGC_GEMINI_MODEL` | Exact deployed Gemini model name; no silent default |
| `AIGC_GEMINI_EVIDENCE_BACKEND` | `gcs` in production |
| `AIGC_GEMINI_EVIDENCE_BUCKET` | Dedicated evidence bucket |
| `AIGC_GEMINI_EVIDENCE_PREFIX` | Defaults to `product-evidence/gemini` |
| `AIGC_GEMINI_CONTROL_DSN_SECRET_REF` | Exact numeric Secret Manager version for the durable PostgreSQL control store |
| `AIGC_OPERATOR_*_SECRET_REF` | Separate exact-version operator token and principal-binding references |
| `AIGC_RUNTIME_ADMIN_*_SECRET_REF` | Pairwise-distinct runtime-admin token and binding references |
| `AIGC_JUDGE_*_SECRET_REF` | Judge-only token and binding references used only by the judge surface |
| `AIGC_SECRET_ACCESS_MANIFEST_PATH` | Container path to the governed purpose-to-reference manifest |
| `AIGC_DEPLOYMENT_AUTHORIZATION_SHA256` | Canonical hash binding secret access to the reviewed deployment authorization |
| `AIGC_GEMINI_TIMEOUT_SECONDS` | Hard SDK request timeout; defaults to `30` |
| `AIGC_GEMINI_MAX_OUTPUT_TOKENS` | Bounded output budget; defaults to `1200` |
| `AIGC_GEMINI_MAX_ATTEMPTS` | Exactly `1` in production; no hidden provider retry |
| `AIGC_ENV` | `production` on Cloud Run |
| `K_REVISION` | Cloud Run-provided runtime revision; required in production |

Production refuses the JSONL evidence backend because Cloud Run's writable
filesystem is ephemeral.

## Service identity

Use separate operator and judge Cloud Run service accounts. Grant the operator
only the minimum Vertex prediction, Cloud SQL, evidence-object, and exact-secret
access required by the reviewed design. The judge identity must have no Vertex
permission, control-store write permission, or operator/runtime-admin secret
access; it reads only the sanitized receipt prefix. Do not create or commit a
service-account key file.

The staging deployment helper requires an unexpired, exact-target authorization
for the project, Canadian regions, model, Artifact Registry repository, Cloud
SQL instance, evidence buckets, separate service accounts, exact numeric secret
versions, IAM review, and CAD ceiling. The committed example is default-deny
and cannot authorize an action.

After a separately stored authorization passes, the helper performs read-only
prerequisite inspections, requires the exact clean Git revision, builds the
allowlisted container, resolves the registry digest, and deploys separate
private operator and judge candidates by digest with no traffic. It never
creates foundational resources or changes traffic. Running it with `--execute`
is an external action and requires explicit authorization.

The container runs as an unprivileged `aigc` user. Its Docker and Cloud Build
contexts use exact file allowlists rather than copying the repository. The
deploy command bounds instances, concurrency, and request timeout; those values
are policy inputs, not proof of load capacity.

## API

- `GET /api/gemini/status`
- `GET /api/gemini/runtime/emergency-stop`
- `POST /api/gemini/runtime/emergency-stop`
- `POST /api/gemini/runtime/emergency-stop/clear`
- `POST /api/gemini/workflows`
- `GET /api/gemini/workflows/{run_id}`
- `POST /api/gemini/workflows/{run_id}/decision`
- judge surface only: `GET /api/judge/receipts/{receipt_id}`

Operator routes require `X-AIGC-Operator-Token`; clearing the stop requires the
separate `X-AIGC-Runtime-Admin-Token`; the judge read requires
`X-AIGC-Judge-Token`. In production, `Authorization` remains reserved for Cloud
Run IAM. The attested operator or judge label is not a trusted identity and
does not define the stable rate-limit principal.

Minimal synthetic intake shape (the controlled staging fixture is
`config/gemini_canary_intake.example.json`):

```json
{
  "title": "Synthetic permissioned opportunity",
  "description": "Assess a fictional internal opportunity using only this synthetic description.",
  "source_url": "https://example.com/controlled-example",
  "constraints": ["No external business action", "Human review required"],
  "ai_assistance_permitted": true,
  "ai_disclosure_required": true
}
```

## Validation

```bash
python -m pytest
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
- `human_review_required: true`; if a completed operator review is claimed,
  its generation-bound decision receipt and release/assessment bindings;
- durable Cloud Storage evidence object identifiers;
- redacted screenshot or dashboard view;
- exact Git revision and passing CI;
- customer consent where a real customer input is used.

## Critical activation blockers

Repository implementation of the browser flow does not remove these activation
blockers:

- a passing hosted CI receipt for the exact release SHA;
- an explicitly authorized and inspected Canadian staging configuration;
- an immutable-digest deployment receipt for both no-traffic candidates;
- server-side atomic consumption of a one-use live-model permit bound to actor,
  tenant, request/model/prompt/schema/policy digests, revision, expiry, stop
  epoch, and usage ceiling; the canary script's client-side validation is not
  sufficient production enforcement;
- a least-privilege evidence read/index design that resolves the current
  conflict between create-only writer IAM and workflow retrieval that lists
  Cloud Storage objects;
- one server-permitted synthetic live runtime receipt;
- one explicitly authorized sanitized judge receipt and redacted media
  manifest;
- PR approval, required-check success and merge receipt; and
- a reviewed Devpost preview and submission confirmation.

Until those receipts exist, keep the PR draft and describe the feature as
repository-implemented and locally test-covered, not as deployed, publicly
available, merged, or competition-submitted. See
`docs/GEMINI_REQUIREMENTS_EVIDENCE_MATRIX.md` for the exact claim boundaries.

The shared role token proves possession of that credential and records a
domain-separated principal identifier using a separate binding key. The raw
label and binding key are not written to workflow evidence. This does not
independently prove that the actor was human. Do not describe the event as
verified human identity without a separately evidenced identity provider and
trusted principal.

Model evidence pointers prove only that the cited input field existed. The
input itself is operator-supplied and not externally verified; structured
output does not prove the truth of the source material.

The generation-time `if_generation_match=0` precondition prevents accidental
overwrite of an existing event object. A production claim of retention,
tamper-resistance, or regulatory immutability additionally requires reviewed
bucket IAM, retention-policy, and audit-log evidence.
