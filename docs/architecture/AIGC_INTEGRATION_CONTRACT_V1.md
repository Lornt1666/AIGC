# AIGC_INTEGRATION_CONTRACT_V1

Status: FROZEN_V1
Release train: `release/aigc-nexus-v1`

## Constitutional separation

`Reasoning != Verification != Authority != Execution != Evidence`

1. Default deny is absolute.
2. No agent may self-authorize.
3. Evidence never grants authority.
4. The Verifier is read-only.
5. Canonical hashing binds state transitions.
6. Consequential execution is idempotent.
7. Credentials are resolved by a credential broker and never embedded in an ExecutionPermit.
8. External reality is updated from observed ExecutionReceipts, never from proposed ChangeSets alone.

## Canonical protocol

`WorkOrder -> ContextEnvelope -> ArtifactState -> ChangeSet -> VerifierReport -> GovernanceDecision -> ExecutionPermit -> ToolInvocationRequest -> ExecutionReceipt -> ArtifactState`

### ArtifactState
Immutable, content-addressed canonical epistemic/observed state. It contains no credentials or execution authority.

### ChangeSet
A non-authoritative proposed transition. Every ChangeSet MUST bind `parent_state_hash` to the exact ArtifactState from which it was derived. A stale parent hash is an optimistic-concurrency conflict and MUST NOT be promoted.

### VerifierReport
Read-only evaluation. Deterministic checks execute before any optional cognitive/model-assisted review. The Verifier cannot alter the candidate artifact, grant authority, or execute tools.

### GovernanceDecision
The sole promotion decision envelope. Human and policy decisions use the same contract and are distinguished by `authority_source` (`HUMAN` or `POLICY`). A decision is bound to exact artifact, ChangeSet, verifier, policy, and revision digests.

### ExecutionPermit
A bounded authority descriptor. It contains capability, exact resource scope, expiry, invocation ceiling, and request/change-set bindings. It MUST NOT contain credentials.

### ToolInvocationRequest
The exact execution vector. The ToolBroker assigns effect class and data classification; the requesting agent cannot self-declare a safer class.

Effect classes:
- `PURE`
- `READ_LOCAL`
- `READ_EXTERNAL`
- `WRITE_REVERSIBLE`
- `WRITE_COMPENSATABLE`
- `WRITE_IRREVERSIBLE`
- `FINANCIAL`
- `COMMUNICATION`
- `DEPLOYMENT`
- `SECURITY_SENSITIVE`

Read operations remain governed. They may follow a lighter policy path, but data scope, egress, purpose, rate, record, and sensitivity constraints remain enforceable.

### ExecutionReceipt
Empirical record of what actually happened. Operation-level statuses are authoritative for external-state reconciliation.

Execution status:
- `not_started`
- `succeeded`
- `failed`
- `partially_applied`
- `cancelled`
- `timed_out`
- `indeterminate`

An `indeterminate` result requires read-only reconciliation before retry. A partial result produces an observed partial ArtifactState and a new governed reconciliation ChangeSet; the system MUST NOT pretend atomic rollback occurred.

## Trust-boundary calculus

For canonical state `S_n` and proposed ChangeSet `Delta_n`:

`Hash(S_n) == Delta_n.parent_state_hash`

Promotion:

`Permit_n = Govern(Verify(S_n, Delta_n))`

Credential resolution:

`Credential_n = CredentialBroker(Permit_n)`

Observed transition:

`S_(n+1) = Reduce(S_n, ExecutionReceipt_n)`

Never:

`AgentOutput => Execution`

## Partial failure and reconciliation

A partially applied execution records every operation independently as succeeded, failed, not attempted, timed out, cancelled, or indeterminate. Successful effects are reflected in canonical observed state. Failed/not-attempted effects remain unresolved. Recovery is represented as a new `ChangeSet(change_type=reconciliation)` bound to the post-execution state hash and the triggering receipt.

Automatic destructive rollback is prohibited unless rollback itself is separately represented, verified, authorized, idempotent, and receipted.

## Dynamic cognitive topology

Constitutional roles remain stable:
- Architect
- Critic
- Synthesizer
- Verifier

Domain specialists are selected dynamically from the WorkOrder and may include software, security, testing, cloud, UX, mechanical, electrical, controls, thermal, manufacturing, safety, research, finance, legal/compliance, product, and operations roles.

Specialists produce proposals/evidence only. Cognitive role does not imply execution authority.

## Release-train promotion

`IDEA -> WORK_ORDER -> BUILD -> CANDIDATE -> GOVERNED_REVIEW -> RELEASE_TRAIN -> EXACT_HEAD_CI -> MAIN`

The Nexus V1 release train may integrate bounded workstreams in parallel against this contract. The release train does not authorize direct main writes, automatic merge, production activation, cloud mutation, external communication, financial action, or live provider/model calls.

## Freeze rule

This V1 contract is frozen for Nexus V1 implementation. Changes require an explicit versioned amendment with compatibility analysis. Implementation details may evolve without changing these invariants or canonical object semantics.
