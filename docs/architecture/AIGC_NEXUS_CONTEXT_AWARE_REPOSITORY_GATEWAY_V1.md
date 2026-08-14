# AIGC Nexus Context-Aware Projection & Repository Gateway V1

Status: DETERMINISTIC FOUNDATION — NO LIVE REPOSITORY OR MODEL CALLS

## Constitutional boundary

`Reasoning != Verification != Authority != Execution != Evidence`

Context projection, repository content, provider output, memory, and evidence are non-authoritative. Canonical authority remains `GovernanceDecision -> ExecutionPermit`.

## Topology

```text
WorkOrder
  -> existing ContextEnvelope / Memory+Evidence projection
  -> ArticulationController
  -> ContributionContextProjection
       -> UNTRUSTED_PARENT_ARTICULATION_CONTEXT
       -> UNTRUSTED_REPOSITORY_CONTENT
  -> ContributionRequest
  -> GovernedProviderContributionResolver
  -> NexusProviderRuntime
  -> OfflineDeterministicProviderAdapter
```

Repository foundation:

```text
RepositoryReadRequest
  -> NexusRepositoryGateway
  -> RepositoryReadPort
  -> DeterministicRepositoryReadPort
  -> RepositoryContext
```

The existing `src/core/nexus/context_projection.py` remains the upstream Memory/Evidence selector and is not replaced.

## Parent articulation context

During critique mode the controller now projects the actual opposite proposal into the critique request. Before projection, the source `ArticulationMessage.canonical_hash` is recomputed and verified. The provider-visible copy is then redacted and receives a separate projected-content digest. This intentionally distinguishes source provenance from redacted projection identity.

The projection is explicitly classified `UNTRUSTED_PARENT_ARTICULATION_CONTEXT`; authority and external-action flags remain false.

Deterministic Nexus synthesis remains internal PURE computation and is not represented as a provider call.

## Repository context

`RepositoryReadRequest` always names an explicit repository, exact revision, closed operation, path/query, and sensitivity. `NexusRepositoryGateway` applies repository, operation, path-prefix, sensitivity, and response-size allowlists.

Every observation must prove `observed_revision == requested exact_revision` and its raw byte SHA-256 must match before content is admitted. Provider-visible repository content is redacted, classified `UNTRUSTED_REPOSITORY_CONTENT`, and retains both raw and projected content hashes.

`RepositoryContext` identity is content-addressed over repository, exact revision, ordered projected records, and gateway-policy identity. It is non-authoritative and permanently exposes `write_capability_present = false`.

## External reads remain disabled

This gate implements only `DeterministicRepositoryReadPort`:

- `external_read = false`
- `credentials_required = false`
- `write_capability_present = false`
- network calls = 0
- credential use = 0
- live repository reads = 0
- repository writes = 0
- spend = CAD 0.00

`NexusRepositoryGateway` rejects a port that is write-capable. It also rejects external or credential-requiring ports while `external_reads_enabled = false`.

The historical `GovernedGitHubKernelAdapter` remains unchanged and preserved for a later governed external-read activation. No second unrestricted GitHub client is introduced.

## Provider binding

`GovernedProviderContributionResolver` accepts an optional pre-bound `RepositoryContext`. A bare `repository_context_id` is insufficient. When repository context is requested, the resolver requires:

```text
request.repository_context_id
== prebound RepositoryContext.context_id

RepositoryContext.exact_revision
== resolver.exact_revision
== ProviderInvocation.exact_revision
```

The complete `ContributionContextProjection` is serialized into `ProviderInvocation.input_payload`, which already participates in the canonical request digest and idempotency identity. Therefore changing parent or repository context changes provider request provenance.

Context cannot alter principal, provider, effect class, exact revision, ChangeSet identity, permits, runtime limits, or governance.

## Future activation

A later, separately authorized gate may adapt the existing governed GitHub read-only capability behind `RepositoryReadPort`:

```text
Governance / READ_EXTERNAL authority
  -> ExecutionPermit
  -> ToolBroker
  -> NexusRepositoryGateway
  -> RepositoryReadPort
  -> GovernedGitHubKernelAdapter
  -> GitHub
```

That future activation must preserve read-only permissions, credential isolation, exact-revision binding, redaction, bounded response size, receipt binding, and fail-closed indeterminate outcome semantics.

## Explicitly absent

- live GitHub API calls
- GitHub PAT/App-token handling
- live Gemini/OpenAI calls
- provider credentials
- MCP/A2A servers
- repository mutation
- cloud mutation
- production activation
- financial spend

This document describes a deterministic foundation only; fixture repository observations are not represented as live private-GitHub evidence.
