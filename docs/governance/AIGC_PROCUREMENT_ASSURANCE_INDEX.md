# AIGC Procurement and Assurance Index

This index connects AIGC governance, assurance, identity, persistence, readiness and evolution procurements into one reviewable implementation register.

## Governing documents

- `constitution/AIGC_ENGINEERING_CONSTITUTION.md` — AEC-001 human-readable authority.
- `programs/AIGC_EIAP_ASSURANCE_PROGRAM.md` — engineering intelligence and assurance program.
- `standards/AIGC_EIAP_SHARED_ASSURANCE_CONTRACTS_STANDARD.md` — shared evidence contracts.
- `standards/AIGC_ASSURANCE_SENSORIUM_STANDARD.md` — deterministic observation and finding synthesis.
- `standards/AIGC_REVIEW_PACKET_STANDARD.md` — revision-bound review packet requirements.
- `charters/AIGC_ENGINEERING_REVIEW_COUNCIL_CHARTER.md` — human review council model.
- `policies/AIGC_REVIEW_AUTHORITY_AND_EXTERNAL_ASSURANCE_POLICY.md` — review authority classes.
- `procedures/AIGC_ZERO_AMBIGUITY_PROCUREMENT_WORKFLOW.md` — bounded procurement procedure.
- `procedures/AIGC_ASSURANCE_IMPLEMENTATION_CHECKLIST.md` — implementation gates.
- `procedures/AIGC_DUAL_REVISION_CI_EVIDENCE_PROCEDURE_V2.md` — immutable-head and merge-candidate assurance procedure.
- `programs/AIGC_UPEP_001.md` — universal lifecycle from intent through retirement.

## Current authoritative mainline

At creation of the dual-revision evidence branch, current `main` was:

`293de53489fe7212fad272c01c698c0ffe2da610`

That revision includes the merged localhost operator API and transactional SQLite authority, receipt, audit, migration, integrity and backup substrate. These are non-production internal capabilities; they do not authorize public networking, production identity, credentials, deployment or external action.

## Current implementation register

| Capability train | Repository state | Evidence state | Next controlled action |
|---|---|---|---|
| AEC-001 constitutional substrate | merged and ratified in machine governance records | repository validation exists | maintain and reconcile any human/machine document mismatch separately |
| EIAP shared assurance contracts | merged | deterministic tests exist | extend through bounded consumers |
| Assurance Sensorium v1 | merged | local deterministic evidence | operational adapters later |
| Review Packet Generator v1 | merged | revision-reference tests | consume dual-revision evidence later |
| Principal Authority Binding runtime v1.1 | merged through PR #50 | local synthetic authorization evidence | production identity remains blocked |
| Local operator API | merged through PR #54 as `70eb171d3f7144917f72a68cd2ca8987efd42a27` | localhost tests and prior exact-head CI | preserve non-production boundary |
| Transactional local authority and audit persistence | merged through PR #61 as `293de53489fe7212fad272c01c698c0ffe2da610` | migration, integrity, concurrency, immutability and backup tests | wire bounded consumers through separate PRs |
| Dual-Revision CI Evidence Gate v2, PR #69 | draft on `codex/ci-dual-revision-evidence-gate-v2-current-main` | both evidence lanes demonstrated successfully; fresh evidence remains mandatory for the final head | operator review and separate merge decision |
| PR #53 Exact Revision Evidence Gate v1 | closed unmerged as superseded | run 671 remains valid historical evidence for its older immutable head | retain as historical reference only |
| Persistent authorization receipt API, PR #63 | draft | successful tests but synthetic-merge readiness artifact | remain blocked pending fresh v2 evidence |
| Governed job state-machine kernel, PR #64 | draft | successful tests but synthetic-merge readiness artifact | remain blocked pending v2 and lifecycle reconciliation |
| Canonical job lifecycle contract, PR #65 | draft | successful tests but synthetic-merge readiness artifact | remain blocked pending v2 and Issue #66 decision |
| Production identity, approved connectors and deployment | blocked | no production evidence | remain deferred |

## Evidence-role model

AIGC now distinguishes:

- `immutable_checked_out_revision` — proves the exact reviewed source revision;
- `pull_request_merge_candidate` — proves the reviewed head integrates with the event target revision.

Neither evidence class substitutes for the other.

## Current gating dependency

```text
Dual-Revision CI Evidence Gate v2
→ immutable-head receipt and readiness artifact
→ merge-candidate equality and ancestry receipt
→ operator review of final immutable head
→ separately authorized expected-head-protected merge
→ exact-main post-merge verification
→ fresh evidence for selected downstream PRs
```

CI success is evidence, not approval or merge authority.

## PR #53 disposition

PR #53 is `SUPERSEDED_CLOSED_UNMERGED`.

PR #69 reconstructed the evidence boundary from current `main` and demonstrated successful immutable-head and merge-candidate lanes. PR #53 was then closed without merge. Its stale-base procurement index and workflow history remain reference evidence only and must not be reintroduced as current repository state.

## Blocking downstream state

PRs #63, #64 and #65 remain non-merge-ready until fresh immutable-head and merge-candidate evidence is produced on their final heads.

Issue #66 remains open and independently blocking. The accountable operator must decide:

- distinct `WORK_ACCEPTED` and `ACCEPTED_FOR_DELIVERY` semantics;
- explicit `REWORK_REQUIRED` versus compressed adapter semantics;
- PR #64 expansion, reclassification or discontinuation.

CI cannot make those semantic decisions.

## Prioritized transformation backlog

1. Confirm fresh dual-revision CI evidence on the final PR #69 head.
2. Obtain operator review and an explicit merge decision.
3. Perform exact-main post-merge verification if merge is authorized.
4. Resolve Issue #66 through an attributable operator decision.
5. Re-run or refresh PRs #63–#65 in dependency order.
6. Reconcile the production-readiness ledger against merged API and persistence evidence in a separate PR.
7. Build a unified `CapabilityEvidenceSnapshot v1` consumed by readiness and recursive evolution.
8. Continue production identity, monitoring, recovery, approved connectors and deployment only through separate reviewed trains.

## Authority and maturity statement

Repository documents, schemas, local code and CI tests do not prove staging, production, certification, legal compliance, independent human review or safe external operation. Every consequential implementation requires bounded scope, immutable evidence, target-branch integration evidence, applicable review authority, operator-controlled merge, rollback and post-merge verification.

AIGC distinguishes automated verification, AI advisory review, operator ratification, independent external assurance and independent human review. These events are not interchangeable.

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
- Immutable-head and merge-candidate evidence remain distinct.
- CI success is not merge approval.

## Current review checklist

- [ ] immutable selected and checked-out revisions are equal;
- [ ] immutable receipt, readiness source revision and artifact name identify the same final head;
- [ ] merge expected and checked-out revisions are equal;
- [ ] event base and immutable final head are ancestors of the merge candidate;
- [ ] both CI jobs pass on the final immutable head;
- [ ] no unresolved blocking finding or review thread remains;
- [ ] Security & Privacy Wiring remains intact;
- [ ] workflow permissions remain read-only and checkout credentials are not persisted;
- [ ] no production identity, credential, deployment, connector or external action is introduced;
- [ ] operator authority and residual-risk acceptance are explicit;
- [ ] rollback is bounded;
- [ ] post-merge exact-main verification is planned;
- [ ] readiness changes occur only in a separate evidence-backed update.
