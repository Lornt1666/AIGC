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
| AEC-001 constitutional substrate | merged and ratified | exact revision and CI receipts recorded | maintain and enforce |
| EIAP shared assurance contracts | merged | tested in CI | extend through bounded consumers |
| Assurance Sensorium v1 | merged | local deterministic tests | operational adapters later |
| Review Packet Generator v1 | merged | exact-reference tests | integrate further review evidence |
| Identity Scope Authorization Kernel v1 | merged | local simulator only | superseded semantically by v1.1 correction train |
| Principal Authority Binding Forge v1.1 contracts | merged through PR #49 | procurement and schemas on main | preserve as authority contract |
| Principal Authority Binding runtime v1.1 | open PR #50 | CI run 633 passed, but uploaded readiness receipt names the synthetic merge revision rather than the PR head | revalidate after exact-revision CI correction |
| Exact Revision Evidence Gate v1 | separate branch `codex/ci-exact-revision-evidence-gate-v1` | implementation and tests pending final CI | draft PR, review, expected-head merge, exact-main verification |
| Production Readiness Ledger | merged | 53.9/100 structural evidence on run 633; not operational proof | reconcile only after exact-main identity evidence |
| Transactional identity persistence | not started | no durable database evidence | next capability train after identity integration |
| Production identity, connectors, deployment | blocked | no production evidence | remain deferred |

## Current gating dependency

The immediate dependency is trustworthy revision binding:

```text
Exact Revision Evidence Gate PR
→ exact-head CI receipt and readiness artifact
→ operator review and controlled merge
→ exact-main verification
→ refresh/revalidate PR #50 on its exact head
→ operator-controlled PR #50 merge decision
→ exact-main identity verification
→ separate readiness-ledger reconciliation to at most partial
→ transactional identity persistence procurement
```

No production capability may be inferred from passing CI. CI supplies evidence; it does not grant authority.

## Prioritized transformation backlog

1. Exact Revision Evidence Gate v1.
2. PR #50 exact-head revalidation and controlled integration.
3. Readiness-ledger reconciliation with production blocker retained.
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
- [ ] rollback is bounded and tested conceptually;
- [ ] post-merge exact-main verification is planned;
- [ ] readiness changes occur only in a separate evidence-backed update;
- [ ] public-facing explanations remain understandable and accessible.
