# AIGC Nexus V1 Release Readiness Evidence Packet

Status: `PRE-RELEASE EVIDENCE — NOT READY FOR GOVERNED MERGE`

Prepared from admitted implementation baseline:

- PR: `#181`
- integration branch: `release/aigc-nexus-v1`
- admitted head before this packet: `20385f1e5fab01d78579afd6af25348065be4481`
- exact-head CI: `AIGC CI #2674`
- workflow run ID: `31239927750`
- retained artifact ID: `9016695906`
- retained artifact digest: `sha256:bee233ee2f6cb6904cb8ace31dff42dbf70050a193acd1bd40b44c4a3f4bed53`
- tested tree: `ef9ce71e62ee7ae3f13f5393d6c7a9e0164c1aa2`
- current-main parent already converged into the release train: `60297f4c6ac1c0feecb5ab913991cf3220247f27`

The commit containing this packet and the absorbed Québec foundation requires its own fresh exact-head CI receipt before either may be treated as admitted.

## Constitutional release rule

`Reasoning != Verification != Authority != Execution != Evidence`

CI success, repository evidence, provider output, infrastructure plans, credentials, and deployment receipts do not grant release authority. PR #181 remains draft until all declared release blockers are resolved and a separate release disposition is issued.

## Completion matrix

| # | Required capability | Repository implementation | Runtime / external proof | Current disposition |
|---|---|---|---|---|
| 1 | One live private-GitHub `READ_FILE` canary | Implemented and one-shot bounded | Attempt reached the canary execution step, but the inner receipt was not retained and dispatch cannot be ruled out | `INDETERMINATE — NO RETRY` |
| 2 | GitHub App production credential boundary | Implemented: repository-scoped installation-token architecture, read-only permission checks, opaque capability | No real App installation/private key provisioned in repository runtime | `IMPLEMENTED / EXTERNAL PROVISIONING REQUIRED` |
| 3 | Gemini adapter behind NexusProviderRuntime | Implemented behind explicit live runtime policy and actual `ExecutionPermit`; Vertex ADC/workload-identity design | No verified Google project/workload identity available to this execution environment | `IMPLEMENTED / LIVE CANARY BLOCKED` |
| 4 | OpenAI adapter behind same runtime | Implemented Responses API adapter, exact model, `store=false`, no tools, usage/cost evidence | No safely injected OpenAI project key available to AIGC CI/staging | `IMPLEMENTED / LIVE CANARY BLOCKED` |
| 5 | Durable runtime controls | PostgreSQL transactional stop epoch, idempotency, usage/rate budgets, permit counters, terminal result persistence | CI #2674 exercised a real PostgreSQL 16 service and the full suite passed | `ADMITTED` |
| 6 | Controlled live Gemini/OpenAI canary | Runtime/adapters ready | Blocked by missing external provider identities and safe secret injection | `BLOCKED EXTERNALLY` |
| 7 | Staging deployment by immutable digest | Québec plan-first foundation is absorbed by the commit containing this packet; governed deployment procedure exists historically | No verified GCP staging project/billing/WIF/secrets/notification channels/image digest | `FOUNDATION READY / APPLY BLOCKED` |
| 8 | Load/failure/security/reconciliation on deployed system | Local/CI adversarial and failure semantics are extensive | Cannot claim deployed load/SRE proof before staging exists | `BLOCKED BY #7` |
| 9 | Full-system convergence review | Current main is a parent of PR #181; Colosseum + Nexus coexist under current exact-head CI; no repository-wide TODO/FIXME/NotImplemented markers found in connector search | Legacy overlapping PR/file generations still carry evidence and are not proven deletion-safe | `CONVERGED FOR RELEASE TRAIN / RETIREMENT DEBT DEFERRED` |
| 10 | Release packet → ready → governed merge → post-merge verification | This packet provides the pre-release evidence ledger | Ready/merge remain prohibited while items 1, 6, 7 and 8 lack conclusive runtime evidence | `BLOCKED` |

## Exact-head CI evidence at admitted baseline

AIGC CI #2674 passed the shared canonical exact-SHA contract at `20385f1e5fab01d78579afd6af25348065be4481`.

The retained stage evidence records success for:

- contracts and canonical validation;
- full repository tests with zero failed/error tests;
- PostgreSQL-backed Nexus runtime-control integration tests;
- Python compilation;
- provider-discovery guard;
- dependency `pip check`;
- repository redaction scan with zero findings;
- release secret scan with zero findings;
- Terraform inertness;
- Colosseum schema validation;
- Colosseum serialization round trips;
- false-authority verification;
- procurement smoke tests;
- readiness validation.

The admission receipt explicitly records:

```text
external_authority_granted = false
live_model_call_authority_granted = false
deployment_authority_granted = false
financial_authority_granted = false
merge_authority_granted = false
```

Those fields are release blockers, not documentation noise.

## Private GitHub read canary disposition

The previously authorized single live private-GitHub read was intentionally one-shot and no-retry.

The canary reached the repository-read execution path after canonical validation, then raised `GovernedRepositoryReadError`. The workflow did not persist the inner `ExecutionReceipt` before propagation. Because a network dispatch cannot be ruled out from retained evidence, the only valid classification is:

```text
execution_status = INDETERMINATE
reconciliation_required = true
automatic_retry = false
```

The canonical workflow was immediately relocked and contains no live repository-read step. Do not retry that canary under the consumed authority.

## GitHub production credential boundary

The production implementation uses a GitHub App installation boundary rather than a PAT or model-visible token.

Target properties:

- repository-scoped installation;
- short-lived App JWT only inside infrastructure credential resolution;
- short-lived installation access token only inside transport;
- requested repository list restricted to `Lornt1666/AIGC`;
- effective `contents: read` permission;
- any returned non-read permission fails closed;
- private key and installation token never enter Nexus contracts, permits, contexts, model input, receipts, or repository evidence;
- token cleared after the governed read.

Provisioning an actual GitHub App installation/private key is an external operations task and is not represented as complete merely because the boundary is implemented.

## Live model provider boundary

Both live model adapters are downstream of an explicit `GovernedLiveNexusProviderRuntime` rather than weakening the default runtime.

The default `NexusProviderRuntime` still rejects live/network/credential providers.

The live runtime requires:

- explicit provider allowlist;
- explicit live/network/credential policy flags;
- trusted provider descriptor and exact effect class;
- actual canonical `ExecutionPermit`;
- exact principal/capability/resource/revision/request-digest binding;
- durable control-store health;
- autonomy/consequence assessment;
- emergency-stop epoch;
- atomic idempotency and budgets;
- terminal `ExecutionReceipt`.

The Gemini adapter targets Vertex through ADC/workload identity and has no API-key field. The OpenAI adapter accepts a project key only through an infrastructure callback and calls the Responses API with persistence disabled. Neither adapter hard-codes provider pricing; exact CAD pricing is deployment configuration because price is an external mutable fact.

## Durable runtime-control evidence

`PostgresRuntimeControlStore` persists and transactionally locks:

- emergency-stop state and monotonic epoch;
- invocation reservations and exact state transitions;
- `(principal, idempotency_key) -> request_digest` bindings;
- principal/global minute/day invocation counters;
- reserved/actual usage counters;
- permit invocation counters;
- terminal `ProviderRuntimeExecution` evidence.

The canonical CI provisions ephemeral PostgreSQL 16 and proves cross-instance replay, atomic idempotency conflict, emergency-stop/clear epoch behavior and durable permit ceilings.

This is production-semantics proof of the control store, not proof that a production Cloud SQL instance has been provisioned.

## Québec staging foundation

The commit containing this packet absorbs the reviewed, plan-first Québec Google Cloud foundation from PR #172 into the Nexus release train.

The foundation is intentionally inert and covers Montréal (`northamerica-northeast1`) policy, private PostgreSQL Cloud SQL, Artifact Registry, regional storage/evidence resources, IAM/service identities, KMS, logging/monitoring, billing-budget controls, authorization/manifest/receipt schemas, and associated tests.

It does **not** authorize Terraform apply or service deployment. The following concrete external facts remain unverified/unavailable to this execution environment:

- active Google Cloud staging project ID and project number;
- intended CAD-denominated billing account binding;
- approved nonzero CAD spending ceiling and current pricing estimate;
- Workload Identity / ADC deployment identity;
- exact human/service identity bindings;
- monitoring notification-channel IDs;
- exact regional Secret Manager numeric version references;
- built immutable OCI image digest;
- actual Cloud Run revision and private service URLs;
- live Cloud SQL instance/revision;
- deployment receipt.

No placeholder value may be promoted into production evidence.

## Deployment, load and observability gate

Until the preceding cloud facts exist, this repository may validate Terraform syntax/inertness and local/runtime failure semantics, but it may not truthfully claim:

```text
staging_deployed = true
immutable_image_deployed = true
health_probe_verified = true
readiness_probe_verified = true
live_observability_verified = true
load_test_verified = true
regional_failover_verified = true
production_ready = true
```

Those claims require runtime receipts from actual staging infrastructure.

## Convergence review

### Mainline convergence

Current Colosseum mainline was merged as a real second parent into the Nexus train before the current admitted provider/durable-runtime baseline. PR #181 is mergeable against `main`.

### State reducer

`src/core/nexus/state_reducer.py` intentionally advances epistemic revision only from canonical `ExecutionReceipt` provenance and does not infer provider-specific external semantics from request parameters. This is not a stale TODO: resource-specific reducers remain separate reviewed adapters so proposed state cannot become observed state by inference.

### Legacy migration / deletion debt

`docs/architecture/AIGC_REPOSITORY_MIGRATION_MAP.md` explicitly records that legacy generations carry CI, security, release and architectural evidence and are not presently proven deletion-safe. The correct release posture is therefore **no destructive cleanup before reference/evidence migration proof**.

Retirement/deletion is post-release convergence debt unless a legacy surface becomes an active security or runtime conflict.

### Dashboard/projection debt

No currently retrieved repository evidence establishes a release-blocking write-through dashboard defect. Dashboard/projection surfaces remain non-authoritative. Any stale display data is lower consequence than corrupting canonical execution/state semantics and should be addressed only against concrete failing projection evidence.

### Mutable external parameters

Provider prices, provider model availability, cloud project/billing identifiers, secret versions and deployment image digests are external mutable facts. They must be injected and receipt-bound at deployment time rather than hard-coded to manufacture apparent completion.

## Release disposition

Current release state:

```text
repository_architecture_converged = true
current_main_ancestry_converged = true
canonical_exact_head_ci = PASS at admitted baseline 20385f1e...
github_app_boundary_implemented = true
gemini_adapter_implemented = true
openai_adapter_implemented = true
durable_runtime_controls_implemented = true
durable_runtime_controls_ci_verified = true
quebec_staging_foundation_present = true

private_github_canary = INDETERMINATE
live_gemini_canary = NOT_EXECUTED
live_openai_canary = NOT_EXECUTED
staging_deployment = NOT_EXECUTED
deployed_load_security_reconciliation = NOT_EXECUTED
production_activation = false
ready_for_review = false
merge_authority = false
```

Therefore:

`RELEASE_GATE_AIGC_NEXUS_V1_FINAL = BLOCKED_ON_EXTERNAL_RUNTIME_EVIDENCE`

Do not mark PR #181 ready and do not merge it until the missing external runtime receipts are supplied or the declared V1 release scope is formally amended by a separately reviewed governance decision.
