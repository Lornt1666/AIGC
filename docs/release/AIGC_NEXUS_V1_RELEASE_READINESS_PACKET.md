# AIGC Nexus V1 Release Readiness Evidence Packet

Status: `PRE-RELEASE EVIDENCE COMPLETE — GOVERNED RELEASE STILL BLOCKED ON EXTERNAL RUNTIME PROOF`

## Evidence baseline

This packet is prepared from the latest admitted implementation baseline before the packet update:

- repository: `Lornt1666/AIGC`
- PR: `#181`
- integration branch: `release/aigc-nexus-v1`
- admitted implementation head: `ce17c0292d09e8b3327c77bc8c03630f065bd730`
- tested tree: `2bd3f9e6a834c286acaddce898786f6dcc582a67`
- exact-head workflow: `AIGC CI #2682`
- workflow run ID: `31240929913`
- retained artifact ID: `9017001382`
- retained artifact digest: `sha256:629b276d9ad2956d48f33a0c4277957a9badb9fa536722d2cbe61674bec3ce13`
- local Nexus image ID: `sha256:d897251f0af50b6d2cbe93fb5fe8b5c21461706cb68b987bbb86ee95af573772`
- local container user: `aigc`
- converged current-main parent: `60297f4c6ac1c0feecb5ab913991cf3220247f27`

The commit containing this packet requires its own fresh exact-head CI receipt. The baseline above is evidence for the implementation state that this packet summarizes; it is not authority to bypass the remaining external gates.

## Constitutional release rule

`Reasoning != Verification != Authority != Execution != Evidence`

CI success, code completeness, a container build, credentials, provider output, infrastructure plans, and deployment receipts are all evidence. None independently grants release authority.

`Capability may evolve autonomously. Authority may not.`

## Completion matrix

| # | Required capability | Repository state | External/runtime proof | Disposition |
|---|---|---|---|---|
| 1 | One live private-GitHub `READ_FILE` canary | One-shot governed transport implemented and relocked after the attempt | The canary dispatched through the real GitHub Actions read-only credential/transport boundary and returned past transport-specific HTTP/URL/JSON/base64 failure handling; canonical RepositoryContext admission then failed and the inner receipt was not retained | `TRANSPORT PROVEN / CANONICAL ADMISSION FAILED / NO RETRY` |
| 2 | GitHub App production credential boundary | Repository-scoped installation-token boundary, read-only permission validation and opaque capability implemented/tested | No real GitHub App installation/private-key provisioning receipt in the Nexus runtime | `IMPLEMENTED + CI ADMITTED / EXTERNAL PROVISIONING REQUIRED` |
| 3 | Gemini adapter behind NexusProviderRuntime | Vertex Gemini adapter behind `GovernedLiveNexusProviderRuntime`, exact model, ADC/workload identity, no tools | No verified AIGC Google project/workload identity and no live invocation receipt | `IMPLEMENTED + CI ADMITTED / LIVE CANARY BLOCKED` |
| 4 | OpenAI adapter behind same runtime | Responses adapter behind the same provider-neutral runtime, exact model, `store=false`, no tools | Secure project-key setup is external to repository CI and no safely injected runtime key/live receipt is present | `IMPLEMENTED + CI ADMITTED / LIVE CANARY BLOCKED` |
| 5 | Durable runtime controls | Transactional PostgreSQL stop epoch, idempotency, rate/usage budgets, permit counters and terminal result replay | Ephemeral PostgreSQL 16 integration exercised in exact-head CI | `ADMITTED` |
| 6 | Controlled live Gemini/OpenAI canary | Runtime/adapters/receipts are implemented | Missing verified provider identities, safe runtime secret injection and explicit nonzero canary spend authorization | `BLOCKED EXTERNALLY` |
| 7 | Immutable-digest Québec staging deployment | Nexus runtime API, regional-secret resolver, non-root image, Cloud Build config, exact authorization gate, immutable-digest deployer, no-traffic candidate, health/readiness/observability probes implemented; local image build PASS | No verified project ID/number, WIF identity, exact provisioned resources/secrets, approved staging spend, Artifact Registry digest or Cloud Run revision receipt | `IMPLEMENTATION COMPLETE / DEPLOYMENT NOT EXECUTED` |
| 8 | Load/failure/security/reconciliation validation | Bounded authenticated candidate validation harness implemented; canonical indeterminate reconciliation regression PASS | No deployed candidate URL; therefore no real latency/load/security runtime receipt and no authorized destructive fault injection | `HARNESS COMPLETE / DEPLOYED VALIDATION NOT EXECUTED` |
| 9 | Full-system convergence review | Current main ancestry converged; reducer semantics hardened; dashboard stale capability projection repaired; exact revision UI enforced; direct Python dependencies pinned; Québec foundation + Nexus runtime coexist under one train | Historical retirement and fully hash-locked transitive dependency closure remain post-release hardening debt | `CI-ADMITTED CONVERGENCE` |
| 10 | Release evidence -> ready -> merge -> post-merge verification | This packet is the release evidence ledger; exact-head CI process is available | Gates 6–8 lack real external receipts and item 1 lacks a canonical success receipt | `DO NOT MARK READY / DO NOT MERGE` |

## Exact-head implementation evidence

At `ce17c0292d09e8b3327c77bc8c03630f065bd730`, AIGC CI #2682 passed:

- exact requested checkout and tested-tree binding;
- dependency installation and `pip check`;
- Python compilation;
- canonical contracts;
- full repository tests with zero failed/error tests;
- PostgreSQL-backed Nexus runtime-control integration;
- GitHub App credential-boundary regressions;
- Gemini/OpenAI provider-adapter regressions;
- Québec cloud authorization and location regressions;
- Nexus staging runtime, deployment-plan and deployed-validation harness regressions;
- redaction scan with zero findings;
- release secret scan with zero findings;
- provider-discovery guard;
- Terraform inertness;
- Colosseum schema validation and serialization round trips;
- false-authority verification;
- readiness validation;
- local `Dockerfile.nexus` build with non-root user `aigc`.

Retained admission authority fields remain:

```text
external_authority_granted = false
live_model_call_authority_granted = false
deployment_authority_granted = false
financial_authority_granted = false
merge_authority_granted = false
```

Local container evidence also records:

```text
registry_push_performed = false
cloud_build_performed = false
deployment_performed = false
```

## Private GitHub canary reconciliation

The single authorized private-GitHub canary must not be retried under the consumed authority.

The canary reached the governed read step with GitHub Actions `Contents: read` / `Metadata: read`. The transport boundary consumes its single network authorization immediately before dispatch. HTTP errors, URL/timeout failures, invalid JSON and invalid base64 are normalized as `RepositoryTransportError`; the observed #2666 failure instead propagated through the executor's generic post-execution validation branch. The defensible finding is therefore:

```text
real_private_github_transport_exercised = true
transport_specific_failure_observed = false
canonical_repository_context_admitted = false
canonical_success_receipt_retained = false
automatic_retry = false
```

This proves the real private-repository transport path, but it does not justify claiming a fully successful canonical read canary.

## Credential and provider boundaries

### GitHub

The production target uses a repository-scoped GitHub App installation token rather than a PAT. Private-key and token material remain inside infrastructure and only an opaque capability crosses into the Nexus read path.

### Gemini

The Gemini adapter uses Vertex mode with ADC/workload identity, exact configured model identity, TEXT-only capability, no tool surface and the provider-neutral governed runtime.

### OpenAI

The OpenAI adapter uses the Responses API with persistence disabled and no tool surface. An API key is accepted only through the infrastructure callback; it is never part of `ProviderInvocation`, `ExecutionPermit`, prompts, receipts or evidence.

Both live adapters remain blocked by default `NexusProviderRuntime`. Live execution requires the explicit `GovernedLiveNexusProviderRuntime`, provider allowlist, live/network/credential policy flags, actual request-bound `ExecutionPermit`, durable control-store health, emergency-stop epoch, idempotency, usage/cost limits and canonical terminal receipts.

## Durable runtime controls

`PostgresRuntimeControlStore` is provider-neutral and transactionally persists:

- emergency-stop state and monotonic epoch;
- invocation reservations and state transitions;
- `(principal, idempotency_key) -> request_digest` bindings;
- principal/global minute/day request and usage reservations;
- permit invocation counters;
- terminal `ProviderRuntimeExecution` results.

The exact-head suite proves cross-instance replay, idempotency conflict, emergency-stop activation/clear, durable permit ceilings and fail-closed transitions against PostgreSQL 16.

## Québec staging runtime

The repository now contains:

- `src/webapp/nexus_runtime_api.py` with `/health`, `/ready` and metadata-only `/observability`;
- `src/infrastructure/credentials/regional_secret_manager.py` for exact numeric Montréal regional-secret references;
- `Dockerfile.nexus` non-root runtime image;
- `.gcloudignore.nexus` minimized Cloud Build context;
- `cloudbuild.nexus.yaml`;
- `scripts/deploy_nexus_staging.py`;
- `scripts/validate_nexus_staging_runtime.py`;
- `docs/architecture/AIGC_NEXUS_QUEBEC_STAGING_RUNTIME_V1.md`.

The deployment procedure requires the existing Québec `gate=staging` authorization, exact repository SHA/tree/resource digest, completed reviews, exact service accounts and regional secret versions, then builds regionally, resolves the Artifact Registry digest, deploys the digest with no unauthenticated/no production traffic, attaches private Cloud SQL, configures startup/liveness/readiness probes and verifies the authenticated candidate `/ready` endpoint.

The runtime passes only the regional secret **reference** in configuration; the value is resolved inside the service through the Montréal regional Secret Manager endpoint using managed identity. Raw values are not placed in Cloud Run environment manifests or deployment receipts.

Any failed mutating cloud command is classified as indeterminate and is not automatically retried.

## Gate 8 validation scope

The deployed validation harness is ready to collect real candidate evidence for:

- authenticated health/readiness;
- unauthenticated denial;
- unknown-route fail-closed behavior;
- metadata-only observability;
- bounded concurrent readiness load;
- mean, p50, p95 and maximum latency;
- load failure count;
- canonical indeterminate-receipt reconciliation behavior.

It deliberately does not include a hidden destructive fault-injection backdoor. Stopping a database, activating the durable emergency stop, or otherwise forcing a deployed failure requires a separate bounded fault-injection authorization.

## Full-system convergence findings

Resolved before this packet:

1. Canonical `ArtifactState` advances only after a confirmed successful receipt.
2. `not_started`, `failed`, `cancelled` and `timed_out` receipts do not advance canonical state.
3. `partially_applied` and `indeterminate` receipts require reconciliation before state can advance.
4. Dashboard projection no longer describes admitted memory/provider/Postgres surfaces as missing future work.
5. Visible Nexus dry-run requires an exact hexadecimal evidence revision rather than a mutable branch name.
6. Direct Python dependencies are exact-pinned to the versions admitted by CI.
7. Québec foundation and the Nexus runtime/deployment surface now exist in the same release lineage.
8. The Nexus staging container is buildable and non-root under hosted CI.

Remaining non-blocking repository debt:

- resource-specific state reducers must remain separately reviewed rather than inferring external state from requests;
- dashboard remains inspection-only and not a production authority surface;
- legacy historical branches/files remain evidence-bearing and are not proven deletion-safe;
- a cryptographically hash-locked transitive Python dependency lock is not yet generated.

## External blockers to actual release

The release train still lacks defensible evidence for all of the following:

1. a verified AIGC Google Cloud staging project ID and project number;
2. an approved billing/project binding and explicit nonzero CAD staging/canary spend authorization;
3. configured Workload Identity / ADC deployment identity;
4. completed source-control credential preflight and required Québec review booleans;
5. exact provisioned Montréal resource names and exact regional Secret Manager numeric versions;
6. safely injected OpenAI project credential for AIGC runtime;
7. one controlled live Gemini receipt and one controlled live OpenAI receipt with usage/latency/cost evidence;
8. actual Cloud Build ID + Artifact Registry digest + Cloud Run no-traffic candidate revision;
9. actual `/health` and `/ready` staging receipts;
10. actual deployed load/security validation receipt;
11. separately authorized controlled fault-injection evidence if deployed failure testing is required for final release.

No placeholder may be promoted into release evidence.

## Release disposition

Current repository implementation state is strong enough for the remaining work to be external/runtime procurement rather than missing architecture:

```text
repository_architecture_converged = true
current_main_ancestry_converged = true
github_app_boundary_implemented = true
gemini_adapter_implemented = true
openai_adapter_implemented = true
durable_runtime_controls_implemented = true
quebec_staging_foundation_implemented = true
nexus_staging_runtime_implemented = true
immutable_digest_deployment_procedure_implemented = true
deployed_validation_harness_implemented = true
local_nexus_container_build = PASS

private_github_transport = PROVEN
private_github_canonical_read_receipt = FAILED/NOT_RETAINED
live_gemini_canary = NOT_EXECUTED
live_openai_canary = NOT_EXECUTED
staging_cloud_deployment = NOT_EXECUTED
deployed_load_security_validation = NOT_EXECUTED
production_activation = false
ready_for_review = false
merge_authority = false
```

Therefore:

`RELEASE_GATE_AIGC_NEXUS_V1_FINAL = BLOCKED_ON_EXTERNAL_RUNTIME_EVIDENCE`

PR #181 MUST remain draft and unmerged until the missing external runtime receipts are obtained or the V1 release scope is formally amended by a separately reviewed governance decision.
