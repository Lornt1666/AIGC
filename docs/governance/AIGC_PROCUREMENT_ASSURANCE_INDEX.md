# AIGC Procurement and Assurance Index

This index connects AIGC governance, assurance, identity, readiness, and evolution procurements into one reviewable implementation register.

## Governing documents

- `constitution/AIGC_ENGINEERING_CONSTITUTION.md` — ratified AEC-001 human-readable authority.
- `programs/AIGC_EIAP_ASSURANCE_PROGRAM.md` — integrated engineering intelligence and assurance program.
- `standards/AIGC_EIAP_SHARED_ASSURANCE_CONTRACTS_STANDARD.md` — shared evidence and assurance contracts.
- `standards/AIGC_ASSURANCE_SENSORIUM_STANDARD.md` — deterministic observation and finding synthesis.
- `standards/AIGC_REVIEW_PACKET_STANDARD.md` — exact-revision review packet requirements.
- `charters/AIGC_ENGINEERING_REVIEW_COUNCIL_CHARTER.md` — human review council model.
- `policies/AIGC_REVIEW_AUTHORITY_AND_EXTERNAL_ASSURANCE_POLICY.md` — review authority and alternative-assurance classes.
- `procedures/AIGC_ZERO_AMBIGUITY_PROCUREMENT_WORKFLOW.md` — bounded procurement procedure.
- `procedures/AIGC_ASSURANCE_IMPLEMENTATION_CHECKLIST.md` — implementation gates.
- `procedures/AIGC_INDEPENDENT_REVIEWER_RECRUITMENT_AND_ONBOARDING_PACKET.md` — reviewer onboarding and revocation.
- `programs/AIGC_UPEP_001.md` — universal lifecycle from intent through retirement.

## Current implementation register

| Capability train | Repository state | Evidence state | Next controlled action |
|---|---|---|---|
| AEC-001 constitutional substrate | merged and ratified | repository validation exists | maintain and enforce |
| EIAP shared assurance contracts | merged | tested in CI | extend through bounded consumers |
| Assurance Sensorium v1 | merged | local deterministic tests | operational adapters later |
| Review Packet Generator v1 | merged | revision-reference tests | integrate further review evidence |
| Identity Scope Authorization Kernel v1 | merged | local simulator | retained as predecessor context |
| Principal Authority Binding Forge v1.1 contracts | merged through PR #49 | schemas and procurement on main | preserve as authority contract |
| Principal Authority Binding runtime v1.1 | merged through PR #50 as `532c62150becdc1b0fa606ddeaeb70bc40197574` | run 633 passed; uploaded readiness receipt names synthetic merge revision `63197dc34ba0ef0ff2e8edaa0d3a714541445571`, not PR head | verify integrated main after provenance gate merges |
| Exact Revision Evidence Gate v1 | separate branch `codex/ci-exact-revision-evidence-gate-v1-mainline` | implementation and tests pending final CI | draft PR, inspect artifacts, operator review |
| Production Readiness Ledger | merged | last inspected report 53.9/100 structural evidence; current main not yet revision-bound | reconcile identity to at most `partial` only after exact-main verification |
| Transactional identity persistence | not started | no durable database evidence | next capability train after ledger reconciliation |
| Production identity, approved connectors, deployment | blocked | no production evidence | remain deferred |

## Current gating dependency

The immediate dependency is trustworthy revision binding:

```text
Exact Revision Evidence Gate draft PR
→ exact-head CI receipt and readiness artifact
→ operator review and expected-head-protected squash merge
→ exact-main verification of identity runtime plus provenance gate
→ separate readiness-ledger reconciliation to at most partial
→ transactional identity persistence procurement
```

No production capability may be inferred from passing CI. CI produces evidence; it does not grant authority.

## Prioritized transformation backlog

1. Exact Revision Evidence Gate v1.
2. Exact-main verification of the combined identity runtime and provenance gate.
3. Readiness-ledger reconciliation with `production_identity_access` blocker retained.
4. Contract-first transactional identity persistence and SQLite repositories.
5. Security/Privacy and Observer Authority adapter integration tests.
6. Provenance-aware evidence graph and evidence-strength taxonomy.
7. Triage stale draft PRs #11, #15, and #21.
8. Staging, monitoring, recovery, approved connectors, and deployment.

## Authority and maturity statement

Repository documents, schemas, and local tests do not prove staging, production, certification, compliance, or independent human review. Every implementation requires a bounded branch, CI on the intended immutable revision, review under the applicable authority path, operator-controlled merge, rollback, and post-merge verification.

AIGC distinguishes automated verification, AI advisory review, operator ratification, independent external assurance, and independent human review. These events are not interchangeable.

For bounded, reversible, non-production changes, the Review Authority Policy permits a disclosed operator alternative-assurance path. That path never creates or claims independent human review. Release-critical production work retains the stronger review requirement.

## Shared invariants

- No completion claim without evidence.
- No consequential action without attributable authority.
- No implicit permit.
- No secrets in repository configuration or evidence packets.
- No direct write to `main`.
- No false independence or human-identity claim.
- No blocking finding averaged away.
- No production-ready claim while blocking capabilities remain.
- Every governed change preserves rollback and immutable revision binding.
- Provider contracts never replace least-privilege technical controls.
- CI success is not merge approval.

## Current review checklist

- [ ] expected and checked-out revisions are equal;
- [ ] readiness and evidence receipts identify that same revision;
- [ ] all mandatory CI stages pass;
- [ ] no unresolved blocking finding or review thread remains;
- [ ] Security & Privacy Wiring remains intact;
- [ ] no credential, production data, deployment, or external action is introduced;
- [ ] operator authority and residual-risk acceptance are explicit;
- [ ] rollback is bounded;
- [ ] post-merge exact-main verification is planned;
- [ ] readiness changes occur only in a separate evidence-backed update;
- [ ] public-facing explanations remain understandable and accessible.
