# AIGC EIAP Shared Assurance Contracts Standard

## Status

Proposed Epoch II standard. This document and its accompanying schema and validator do not establish production operation.

## Purpose

Define one canonical vocabulary for assurance actors, artifacts, evidence, decisions, approvals, gate receipts, traceability, findings, and observations across AIGC.

## Contract set

- `ActorReference`
- `ArtifactReference`
- `EvidenceReference`
- `Decision`
- `ApprovalReference`
- `GateReceipt`
- `TraceabilityManifest`
- `Finding`
- `Observation`

## Core invariants

1. Every governed object is versioned.
2. Every decision, finding, receipt, and evidence record is bound to a revision.
3. Human, AI, service, and organizational identities remain distinguishable.
4. Advisory analysis is never represented as independent human approval.
5. Evidence maturity is explicit.
6. Unknown contract types fail closed.
7. Missing constitutional traceability or rollback blocks a manifest.
8. Confidence values are bounded and cannot replace evidence.
9. A blocking finding cannot be averaged away.
10. Shared contracts contain references and metadata, not secrets or unnecessary sensitive payloads.

## Integration order

```text
AEC-001 ratified
→ EIAP shared contracts
→ Assurance Sensorium observations
→ Finding synthesis
→ Review Packet Generator
→ Review Evidence Agent
→ Identity Kernel adapters
→ Documentation and readiness consumers
```

## Compatibility

Version `1.0.0` is the initial contract family. Breaking changes require a new semantic version, migration guidance, compatibility analysis, rollback, constitutional traceability, review, and operator ratification.

## Bounded v1 acceptance

- strict Draft 2020-12 schema exists;
- deterministic validator exists;
- positive and negative tests pass;
- no external action is performed;
- no database migration is introduced;
- no live identity or credential is stored;
- downstream modules remain unimplemented until this contract layer is reviewed and merged.
