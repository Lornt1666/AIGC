# AIGC Nexus Provider Runtime V1

Status: `BOUNDED_PROVIDER_NEUTRAL_FOUNDATION`
Release train: `release/aigc-nexus-v1`

## Purpose

Establish the first canonical `NexusProviderRuntime` beneath existing Nexus governance,
autonomy classification, and provider-blind articulation interfaces.

This runtime is an execution substrate only.

`ProviderRuntime != Governance`

`ProviderRuntime != CredentialBroker`

`ProviderRuntime != Verifier`

`ProviderRuntime != ArtifactState`

`ProviderOutput != Authority`

The frozen Nexus law remains:

`Reasoning != Verification != Authority != Execution != Evidence`

## Preserved surfaces

This increment does not modify the frozen Nexus contracts, articulation domain/controller,
autonomy domain/classifier, ToolBroker, Verifier, or state reducer.

The already-admitted `ContributionResolver` boundary remains the future articulation
integration point.

## Provider-neutral contracts

`ProviderDescriptor` supplies the trusted provider identity, capabilities, minimum effect
class, network/credential requirements, live/offline status, and supported modalities.

`ProviderInvocation` binds:

- exact provider and capability;
- exact source revision;
- canonical request digest;
- idempotency key;
- usage reservation;
- maximum CAD cost;
- resource scope;
- parent state hash;
- ChangeSet identity;
- optional ExecutionPermit reference.

No credential or secret material belongs in the invocation.

`ProviderAttemptResult` preserves the distinction among:

- `not_started`;
- `succeeded`;
- `failed`;
- `timed_out`;
- `indeterminate`.

An attempted provider operation whose outcome cannot be proven is represented as
`indeterminate`, never silently converted to failure or success.

## Trusted effect classification

The provider adapter descriptor defines the minimum effect class.

Caller-supplied effect classification is only a cross-check. A mismatch fails closed.

This prevents a caller from labelling a network or consequential provider as `PURE`.

## Provider registry

`ProviderRegistry` uses explicit adapter registration only.

It provides:

- duplicate-ID rejection;
- adapter/descriptor identity validation;
- fail-closed unknown-provider resolution;
- no arbitrary dynamic import discovery.

The initial canonical adapter is:

`OfflineDeterministicProviderAdapter`

It identifies itself as:

`offline-deterministic-provider-not-live`

and performs no external provider, network, credential, cloud, or financial work.

## Autonomy integration

`NexusProviderRuntime` derives `ActionIntent` from trusted runtime facts and invokes the
existing pure `assess_autonomy(...)` classifier.

Disposition handling:

- `AUTONOMOUS_POLICY_PATH` -> safe execution may continue;
- `AUTONOMOUS_WITHIN_EXISTING_AUTHORITY` -> actual ExecutionPermit validation is required;
- `BLOCK_PENDING_EXPLICIT_AUTHORITY` -> adapter invocation is blocked;
- `READ_ONLY_RECONCILIATION` -> execution/retry is blocked.

`ConsequenceAssessment` remains non-authoritative policy input.

A Boolean or string claiming existing authority is never sufficient. Material execution
requires the actual `ExecutionPermit` object and validates permit identity, principal,
capability, resource scope, exact revision, request digest, expiry, and invocation ceiling.

## Runtime control

The test-only `InMemoryRuntimeControlStore` proves provider-neutral control semantics:

- emergency-stop epoch;
- stale-epoch rejection;
- atomic principal/idempotency binding;
- principal/global minute limits;
- principal/global daily limits;
- usage reservation;
- permit invocation ceilings;
- conservative actual-usage accounting;
- terminal result retention for idempotent replay.

Its health result is explicitly:

`durable = false`

It is not production evidence.

`UnavailableRuntimeControlStore` blocks all runtime operations.

Durable PostgreSQL persistence remains a later release gate.

## Idempotency

Atomic identity:

`principal + idempotency_key -> canonical request digest`

Same key + same digest returns the retained prior result without a second adapter call.

Same key + different digest fails as an idempotency conflict.

`DuplicateIntent != ExecutionSucceeded`

## Runtime limits

`ProviderRuntimeLimits` bounds:

- principal invocations per minute/day;
- global invocations per minute/day;
- principal/global reserved usage per day;
- maximum usage per invocation;
- maximum cost per invocation.

The initial default maximum provider cost is CAD `0.00`.

## Execution receipts

Provider attempts map into the existing canonical `ExecutionReceipt`.

No second final execution-receipt hierarchy is introduced.

`indeterminate` results require:

`reconciliation_required = true`

and the operation is marked non-retryable until reconciliation.

## Current non-scope

This foundation performs no:

- live Gemini call;
- live OpenAI call;
- Vertex AI call;
- OpenAI Responses API call;
- network access;
- credential resolution;
- Secret Manager access;
- private GitHub access;
- MCP server;
- A2A server;
- PostgreSQL deployment;
- Cloud SQL mutation;
- cloud deployment;
- production activation;
- external communication;
- financial spend.

## Historical capability reuse

The design selectively adapts validated ideas from the governed Gemini release candidate,
especially:

- durable emergency-stop epochs;
- idempotent run reservation;
- principal/global request and usage limits;
- conservative usage accounting;
- explicit not-attempted vs attempted-known vs attempted-unknown provider outcomes;
- fail-closed unavailable runtime control.

Gemini-specific naming and global governance are not retained as canonical Nexus architecture.

## Next integration

After fresh exact-head admission, the next bounded layer may implement:

`GovernedProviderContributionResolver`

behind the existing `ContributionResolver` interface:

`ArticulationController -> ContributionResolver -> GovernedProviderContributionResolver -> NexusProviderRuntime`

Provider-specific Gemini/OpenAI adapters, credential brokerage, durable persistence, private
repository reads, and live canaries remain separate consequence-gated release steps.
