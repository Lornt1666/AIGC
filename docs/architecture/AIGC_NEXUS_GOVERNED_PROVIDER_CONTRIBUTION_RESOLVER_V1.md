# AIGC Nexus Governed Provider Contribution Resolver V1

Status: `BOUNDED_OFFLINE_RUNTIME_INTEGRATION`
Release train: `release/aigc-nexus-v1`

## Purpose

Connect the admitted provider-blind articulation subsystem to the admitted
`NexusProviderRuntime` without introducing live providers, credentials, networking,
repository runtime access, cloud resources, production activation, or financial spend.

Canonical topology:

```text
ArticulationController
        ↓
ContributionResolver
        ↓
GovernedProviderContributionResolver
        ↓
NexusProviderRuntime
        ↓
ProviderRegistry
        ↓
OfflineDeterministicProviderAdapter
```

The frozen Nexus law remains:

`Reasoning != Verification != Authority != Execution != Evidence`

## Preserved surfaces

This increment does not modify:

- `src/domain/nexus/contracts.py`;
- `src/domain/nexus/articulation.py`;
- `src/domain/nexus/autonomy.py`;
- `src/core/nexus/articulation_controller.py`;
- `src/core/nexus/autonomy_policy.py`;
- `src/core/epistemic/tool_broker.py`;
- `src/core/epistemic/verifier.py`;
- `src/core/nexus/state_reducer.py`.

`ArticulationController` continues to depend only on the existing structural
`ContributionResolver` interface.

## Provider input provenance

The admitted `ProviderInvocation` is evolved additively with:

```text
input_payload: str = ""
```

The default preserves compatibility with existing Provider Runtime callers.

For governed articulation resolution, `input_payload` is required to contain a canonical
serialized `UNTRUSTED_PROVIDER_INPUT` envelope derived from the pre-bound route and the
existing `ContributionRequest`.

Because `provider_request_digest(...)` hashes the semantic ProviderInvocation and does not
exclude `input_payload`, the exact provider input is bound into:

- canonical request identity;
- idempotency;
- runtime reservation;
- provider attempt;
- canonical ExecutionReceipt.

`ProviderInput != Authority`

## Offline deterministic provider causality

`OfflineDeterministicProviderAdapter` now computes its output from the exact
`ProviderInvocation.input_payload`.

Its output includes an input digest and an explicit `UNTRUSTED_PROVIDER_INPUT_ECHO` marker.
The response digest is computed from the exact returned payload.

Therefore:

```text
different input
→ different request digest
→ different deterministic provider output
→ different response digest
```

No external provider, network, credential, cloud, or financial operation occurs.

## ProviderContributionRoute

`ProviderContributionRoute` is a frozen pre-bound route containing:

- route key;
- provider ID;
- capability;
- model/resource label;
- resource reference;
- purpose;
- bounded prompt;
- reserved usage;
- maximum CAD cost;
- requested effect class;
- uncertainty.

This release gate accepts only:

```text
provider_id = offline_deterministic
requested_effect_class = PURE
maximum_cost_cad = 0.00
```

No route contains credentials or authority.

## Trusted Nexus binding

`GovernedProviderContributionResolver` is constructed with trusted Nexus state:

- WorkOrder;
- ContextEnvelope;
- ChangeSet;
- principal;
- exact revision;
- articulation session ID;
- NexusProviderRuntime;
- authoritative clock;
- pre-bound routes.

Construction validates:

```text
ContextEnvelope.work_order_id == WorkOrder.work_order_id
ChangeSet.work_order_id == WorkOrder.work_order_id
ChangeSet.parent_state_hash == ContextEnvelope.state_hash
```

Provider/model content cannot replace these values.

## Repository context boundary

`NexusRepositoryGateway` is not admitted yet.

Therefore this resolver rejects any non-null:

`ContributionRequest.repository_context_id`.

No repository provenance is claimed or fabricated by this increment.

## Canonical contribution input

Each provider input contains only articulation data plus the route's bounded prompt:

- `classification = UNTRUSTED_PROVIDER_INPUT`;
- bounded prompt;
- session ID;
- round ID;
- role;
- response type;
- parent message IDs;
- articulation timestamp.

This payload cannot modify:

- principal;
- exact revision;
- ChangeSet identity;
- parent state hash;
- provider registry;
- trusted provider effect class;
- permit state;
- runtime limits;
- authority.

## Deterministic identity

The resolver deterministically derives:

- `TREQ-*` request identity;
- `PINV-*` invocation identity;
- 64-character SHA-256 idempotency key;
- canonical provider request digest.

No UUID or wall-clock value is used as request identity.

`ContributionRequest.created_at` remains articulation data. Runtime authority evaluation uses
a separately injected timezone-aware authoritative clock.

## Runtime result mapping

A contribution is emitted only when the Provider Runtime returns a successful execution with:

- successful provider attempt;
- successful canonical ExecutionReceipt;
- response payload;
- response digest;
- zero provider API calls;
- zero network calls;
- zero credential use;
- zero external actions;
- CAD 0.00 spend.

The resulting existing `FixtureContribution` is populated strictly from the runtime result.
Its `evidence_refs` contains the canonical ExecutionReceipt ID.

The resolver never fabricates a contribution after a failed runtime attempt.

## Failure truth

Runtime outcomes:

```text
not_started
failed
timed_out
indeterminate
```

never become successful articulation contributions.

`indeterminate` retains the canonical Nexus requirement:

```text
reconciliation_required = true
automatic retry = false
```

## Idempotent replay

Exact replay of the same bound route and ContributionRequest produces the same invocation,
request digest, idempotency key, provider output, response digest, ExecutionReceipt, and
FixtureContribution.

The Provider Runtime returns its retained result and the offline adapter is not invoked a
second time.

## Parallel articulation

`ArticulationController.run_parallel(...)` can now receive two contributions through:

```text
controller
→ GovernedProviderContributionResolver
→ NexusProviderRuntime
→ OfflineDeterministicProviderAdapter
→ ExecutionReceipt
→ FixtureContribution
→ ArticulationMessage
→ DialogueLedger
```

The controller remains provider-blind.

## Critique articulation and synthesis boundary

For the existing critique ceremony, the four externalizable provider contribution positions
are routed through Provider Runtime:

- Proposal A;
- Proposal B;
- Critique A;
- Critique B.

Their parent message IDs are bound into provider input.

The current controller does **not** expose parent message content to the resolver, so this
increment claims:

`PARENT_LINEAGE_BOUND = true`

and explicitly does not claim:

`LIVE_CONTEXT_AWARE_CROSS_CRITIQUE = true`.

The final deterministic synthesis remains internal Nexus PURE computation in the existing
controller. It is intentionally **not** forced through Provider Runtime because it is not a
provider invocation, and this release gate prohibits controller redesign.

This is the stronger constitutional interpretation:

`ProviderCall = Execution`

but:

`PureInternalSynthesis != ProviderCall`.

## Authority isolation

The resolver cannot:

- issue GovernanceDecision;
- issue ExecutionPermit;
- grant standing authority;
- create ConsequenceAssessment manually;
- downgrade provider effect classification;
- resolve credentials;
- modify runtime limits;
- mutate ArtifactState;
- access repositories;
- invoke live models.

`ProviderOutput != Authority`

`ContributionResolver != Authority`

## Current non-scope

No:

- Gemini adapter;
- OpenAI adapter;
- live provider call;
- provider credential;
- CredentialBroker;
- MCP server;
- A2A server;
- Repository Gateway;
- private GitHub runtime read;
- repository runtime write;
- persistent runtime database;
- PostgreSQL runtime store;
- Cloud SQL;
- cloud mutation;
- production activation;
- external communication;
- financial spend.

## Next bounded evolution

After exact-head admission, the next architectural work should determine whether
context-aware contribution projection and the read-only Nexus Repository Gateway are best
implemented as one bounded context-projection layer or as two separate gates.

Provider-specific Gemini/OpenAI adapters remain downstream of those boundaries.
