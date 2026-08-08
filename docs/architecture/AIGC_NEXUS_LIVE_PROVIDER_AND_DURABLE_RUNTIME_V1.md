# AIGC Nexus Live Providers and Durable Runtime Controls V1

Status: `IMPLEMENTED — LIVE PROVIDER/STAGING CANARIES REQUIRE EXTERNAL CREDENTIAL + CLOUD PRECONDITIONS`

## Constitutional invariants

`Reasoning != Verification != Authority != Execution != Evidence`

The default `NexusProviderRuntime` remains fail closed for live, network-requiring, and credential-requiring adapters. Live provider execution is exposed only through `GovernedLiveNexusProviderRuntime`, which requires an explicit provider allowlist/policy, an actual canonical `ExecutionPermit`, and durable control-store health by default.

No provider adapter may mint a `GovernanceDecision` or `ExecutionPermit`. Provider output, usage metadata, credentials, pricing configuration, and runtime evidence remain non-authoritative.

## Live provider topology

```text
GovernanceDecision
        ↓
ExecutionPermit
        ↓
GovernedLiveNexusProviderRuntime
        ↓
LiveProviderExecutionPolicy
        ↓
Durable RuntimeControlStore
        ↓
ProviderRegistry
        ├── GoogleVertexGeminiAdapter
        └── OpenAIResponsesAdapter
        ↓
ProviderAttemptResult
        ↓
ExecutionReceipt
```

The provider-neutral runtime still verifies exact request digest, trusted provider identity/effect class, capability, permit principal/resource/revision/request binding, autonomy disposition, emergency-stop epoch, idempotency, request/usage limits, and permit invocation ceilings before invoking a live adapter.

## Provider effect model

Both live text adapters are registered as:

```text
effect_class = READ_EXTERNAL
network_required = true
credentials_required = true
live_provider = true
capability = generate.text
supported_modalities = TEXT
```

A successful provider request therefore records `external_action_performed=true` even though no external state mutation is claimed. Attempted failures with an unknown provider outcome become `indeterminate`, require reconciliation, and are not retryable by the canonical receipt.

## Google Vertex Gemini

`GoogleVertexGeminiAdapter` uses the official Google Gen AI client in Vertex mode:

```text
genai.Client(vertexai=True, project=<project>, location=<location>)
```

Authentication is delegated to Google Application Default Credentials / workload identity. No Gemini API key field exists in `ProviderInvocation` or the adapter constructor. The adapter is exact-model and TEXT-only, disables tools, uses deterministic temperature configuration where supported, requires measurable usage metadata, and hashes only normalized returned text into provider evidence.

## OpenAI Responses

`OpenAIResponsesAdapter` receives its project API key only through an infrastructure callback. The key is never represented in Nexus contracts. Requests use the Responses API with persistence disabled:

```text
client.responses.create(
    model=<exact model>,
    input=<bound untrusted input>,
    store=False,
)
```

No tools are supplied by the adapter. The adapter requires measurable input/output usage before successful admission.

## Cost accounting

Provider prices are external facts and are therefore not hard-coded into either adapter. Deployment configuration must supply a `TokenPricing` table in CAD per million input/output tokens. If exact pricing or usage cannot be established, a live call must not be represented as cost-accounted production evidence.

`ProviderRuntimeLimits.maximum_cost_cad_per_invocation` and `ProviderInvocation.maximum_cost_cad` remain hard ceilings enforced before and after provider execution.

## Durable runtime controls

`PostgresRuntimeControlStore` implements the canonical Nexus `RuntimeControlStore` using transactionally locked PostgreSQL rows.

Migration: `migrations/003_nexus_provider_runtime_controls.sql`

Durably persisted controls include:

- singleton emergency-stop state and monotonic stop epoch;
- exact invocation reservation/state;
- `(principal, idempotency_key)` request binding;
- per-principal/global minute/day invocation counters;
- per-principal/global reserved/actual usage counters;
- permit invocation counters;
- terminal `ProviderRuntimeExecution` JSON evidence.

Reservation, execution transition, completion, emergency-stop transitions, and permit/usage accounting use PostgreSQL transactions and row-level locking. `healthcheck()` returns `durable=true` only when the Postgres control state is reachable.

## GitHub App production credential boundary

`GitHubAppInstallationReadBoundary` provides the production credential model for governed private repository reads. It accepts a private-key supplier only inside the infrastructure boundary, creates a short-lived GitHub App JWT, requests an installation token restricted to the configured repository and `contents: read`, validates returned permissions/expiry, and returns only an opaque `RepositoryCredentialCapability` to Nexus.

Neither the GitHub App private key nor installation token enters `RepositoryReadRequest`, `ExecutionPermit`, `RepositoryContext`, provider prompts, or receipts.

The previously attempted one-shot GitHub Actions read canary is **not** re-run by this increment. Its terminal status remains `INDETERMINATE` because the inner failure receipt was not retained and a network attempt could not be ruled out. The canonical workflow has been relocked and contains no live repository-read step.

## CI validation

The canonical CI job provisions an ephemeral PostgreSQL 16 service only for tests and supplies `NEXUS_TEST_POSTGRES_DSN`. The full repository pytest suite therefore exercises the real transactional Postgres control store, including cross-instance replay, idempotency conflict, emergency-stop epoch, and permit invocation ceiling. The service is non-production and contains no persistent user data.

## Explicit non-scope / unresolved external preconditions

This implementation does not itself:

- create or select a Google Cloud project;
- configure Google workload identity;
- create a live Gemini credential;
- create or expose an OpenAI project API key;
- inject provider credentials into GitHub Actions;
- create Québec staging cloud resources;
- deploy Cloud Run or Cloud SQL;
- perform a live Gemini/OpenAI request;
- retry the indeterminate private-GitHub canary;
- merge PR #181.

Those operations require concrete externally provisioned identities/resources and fresh evidence. Repository code must not invent them.

## Production target sequence

```text
IMPLEMENTED:
GitHub App credential boundary
Gemini adapter
OpenAI adapter
PostgreSQL durable runtime controls
        ↓
REQUIRES EXTERNAL PRECONDITIONS:
Google project/workload identity + OpenAI project key boundary
        ↓
controlled one-invocation provider canaries
        ↓
immutable-image staging deployment
        ↓
load/failure/security/reconciliation proof
        ↓
release evidence packet
        ↓
ready-for-review / governed merge / post-merge exact-head verification
```
