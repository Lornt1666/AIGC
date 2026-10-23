# AIGC Responsibility Taking Agent (RX-148) — Executable Closure Workflow Specification

**Status:** REFERENCE IMPLEMENTATION COMMITTED; exact-head CI pending; live GitHub adapter, independent verification, and production authorization are not established.  
**Release disposition:** BLOCK unless every required evidence gate passes and RX-19 issues the sole authorized release decision.  
**Coordinator:** RX-144 (coordination only).  
**Authority:** RX-19 remains the sole release decision authority. This agent cannot approve itself, assign a human reviewer, alter repository protections, merge, deploy, or release.

## 1. Mission
Reconcile the live state of PR #330; construct a gate-by-gate closure matrix; validate evidence freshness, integrity and cross-bindings; identify actionable external dependencies; and assemble a complete packet for RX-19 without granting authority.

## 2. Contract v1.0.0
Input:
- repository full name and PR number;
- live PR metadata from authenticated GitHub API;
- current head SHA and base SHA;
- workflow runs, job outcomes, run attempt IDs and artifact manifests;
- administrator protection readback;
- reviewer assignment, qualification/independence evidence, review findings and retest receipts;
- provenance verification receipt;
- authenticated human acceptance;
- RX-19 endpoint configuration and authenticated receipt, if available;
- policy version and required-gate policy.

Output:
- immutable observation snapshot;
- gate matrix with PASS / BLOCK / STALE / UNVERIFIABLE / NOT_STARTED;
- blocker list with required actor role, prerequisite, evidence contract, acceptance test and invalidation conditions;
- deterministic evidence manifest and digest;
- release disposition (always BLOCK until the independently authorized RX-19 decision is authenticated).

## 3. Gates and acceptance tests
| Gate | Evidence contract | Acceptance test |
|---|---|---|
| G0 Live reconciliation | PR metadata, current head/base SHAs, timestamp and API source | Re-fetch head; all downstream receipts match the current candidate |
| G1 CI | Required run IDs/attempts, job conclusions, tested SHA, artifact IDs/digests | All required jobs passed for exact current head; no required job silently skipped |
| G2 Artifact integrity | Downloaded artifact manifest, SHA-256, run/attempt/SHA binding | Recompute digest and validate all expected files and bindings |
| G3 Effective protection | Authenticated admin readback for base and release branches | Required checks/reviews/bypass settings demonstrably apply |
| G4 Independent review | Authorized reviewer assignment, qualifications, independence, exact SHA/scope | Reviewer is independent; findings are tracked and closed with independent retests |
| G5 Provenance | Signature/issuer verification receipt, repository/workflow/source/predicate/subject digest | All expected claims match; missing or PR-skipped attestation is not PASS |
| G6 Human acceptance | Authenticated approval record | Approval binds exact final SHA, policy version and evidence digest |
| G7 RX-19 handoff | Verified endpoint contract and authenticated receipt for exact packet digest | Receipt proves correct recipient and payload; otherwise HANDOFF_INTERFACE_MISSING |
| G8 Release decision | Authenticated RX-19 decision | Only RX-19 may authorize; any missing/stale gate remains BLOCK |

## 4. Freshness and invalidation
- Any candidate SHA change invalidates exact-head CI, candidate-bound review, acceptance, provenance and evidence packet as applicable.
- Workflow, policy, artifact or signer changes invalidate the dependent receipts according to an explicit dependency map.
- Run ID without attempt ID is insufficient where reruns can change job outcomes.
- SHA-256 proves byte identity relative to a trusted digest, not the producer or build process.
- Unknown, missing, contradictory, unauthenticated or stale evidence never defaults to PASS.

## 5. Tool and authority policy
Read-only GitHub inspection by default. No shell command execution from untrusted task payloads. No dynamic code execution. No automatic reviewer selection or approval. No changes to branch protection. No merge/deploy/release action. Any future write action must use a separately authorized, narrowly scoped adapter and human-approved activation.

## 6. Deterministic behavior
- Canonicalize JSON using UTF-8, sorted keys, fixed separators and a documented schema version before hashing.
- Sort gate records by stable gate ID and blocker records by gate ID then evidence key.
- Include observation time and API provenance, but separate volatile timestamps from the deterministic content digest where reproducibility requires it.
- Validate schemas strictly; reject duplicate IDs, unknown required-gate statuses, malformed SHAs/digests, unexpected repository/workflow identities, contradictory receipts and undeclared dependencies.
- Emit a stable machine-readable result and human-readable blocker report.

## 7. Required negative and failure-injection tests
1. Live PR head differs from cached SHA -> STALE/BLOCK.
2. CI run succeeded for old SHA -> BLOCK.
3. Mandatory job missing or skipped -> BLOCK.
4. Wrong run attempt or artifact digest -> BLOCK.
5. Malformed, duplicate, missing or contradictory manifest fields -> BLOCK.
6. API 403 or empty ruleset response -> UNVERIFIABLE, not PASS.
7. Reviewer absent, non-independent, or scope SHA mismatch -> BLOCK.
8. Finding marked closed without independent retest evidence -> BLOCK.
9. Attestation missing, invalid, wrong signer/workflow/repository/predicate/SHA/digest -> BLOCK.
10. Acceptance missing or bound to a different SHA/digest/policy -> BLOCK.
11. RX-19 endpoint or authenticated receipt missing -> HANDOFF_INTERFACE_MISSING/BLOCK.
12. RX-144 or any other agent attempts to authorize release -> DENY and audit.
13. Network/API timeout, pagination truncation or partial response -> UNVERIFIABLE; do not use cached data as current.
14. Replay of a previously valid receipt after candidate/policy change -> BLOCK.
15. Kill switch / disabled mode -> no mutations or external side effects.

## 8. Operational lifecycle
SPECIFIED -> IMPLEMENTED -> TESTED -> INDEPENDENTLY_VERIFIED -> PRODUCTION_AUTHORIZED are distinct states. Every transition requires its own evidence and authorized actor. This specification alone supports only SPECIFIED.

## 9. Immediate live checkpoint (observed 2026-10-22)
- PR #330: open, draft, not merged.
- Candidate checked: d551006550e6b83acb0b0af7403f95204dab0f30.
- Run #4200 (ID 39847111141): completed/success.
- Review submissions: zero; inline review threads: zero.
- Run #4200 does not establish signed provenance because the attestation job was skipped for the PR event.
- Effective branch protection remains unverified.
- Release disposition: BLOCK.

## 10. Next external action
An authorized repository administrator must supply authenticated effective-protection readback for the PR base and release branches and assign a qualified independent reviewer. RX-148 can validate those records when provided; it cannot create them.

## 11. Reference implementation checkpoint
- Evaluator: `src/aigc_runtime/closure_workflow.py` (pure snapshot validator; deterministic output; no external side effects).
- CLI: `scripts/aigc_closure_check.py <snapshot.json> [--output result.json]`; exits 0 only when all evidence gates including authenticated RX-19 decision pass, and 2 for BLOCK or invalid input.
- Tests: `tests/test_aigc_closure_workflow.py`; CI explicitly invokes this test module and compiles the evaluator/CLI.
- Required snapshot fields include an authenticated live GitHub observation, exact-head CI run attempts, artifact byte/manifest verification from a trusted adapter, authenticated protection readback, independent review/retest, verified provenance, policy-bound human acceptance, RX-19 handoff receipt, and RX-19 decision.
- This evaluator validates the supplied snapshot's claims and cross-bindings; it does not itself call GitHub or cryptographically verify administrator, reviewer, provenance, acceptance, or RX-19 receipts. A trusted acquisition/verification adapter and independent review are required before treating its output as release evidence.
- The evaluator never merges, deploys, activates agents, or performs a release action. An all-PASS result is a report only, not an execution command.
