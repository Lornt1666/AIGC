# AIGC Responsibility Taking Agent — executable closure workflow

**Implementation status:** reference implementation committed; CI validation pending  
**Authority tier:** R0 / coordinator only  
**Default disposition:** BLOCK  
**Release authority:** RX-19 only  
**External side effects:** none

## Purpose

`src/aigc_responsibility_closure.py` evaluates a freshly supplied PR/CI snapshot and candidate-bound evidence receipts into a deterministic gate matrix. It identifies blocked gates, their accountable roles, evidence contracts, and machine-readable reasons. It is designed for safe orchestration and audit preparation, not as a production release controller.

It does **not** query GitHub, authenticate signatures itself, prove that an adapter is trustworthy, assign or authenticate human reviewers, change branch protection, transmit a packet, merge, deploy, or authorize release. A trusted integration must fetch the live state and cryptographically verify receipt authenticity before providing inputs. Untrusted caller-supplied booleans are not proof of authenticity.

## Execution contract

Call `evaluate_closure(snapshot, evaluation_time=..., max_evidence_age_seconds=3600)`. The input requires:

- `pr`: current PR number, state, draft flag, merged flag, and full 40-character lowercase head SHA.
- `ci`: status, conclusion, head SHA, and a positive assertion that all required checks are complete.
- `evidence`: receipts for effective protection, reviewer assignment, independent review, remediation retest, trusted provenance, human acceptance, and RX-19 handoff.
- `evidence_manifest_sha256`: digest of the complete evidence manifest, required to match the human-acceptance and handoff receipts.

Every receipt must include its expected evidence type, exact candidate SHA, `authenticated: true`, `revoked: false`, valid SHA-256 content digest, non-empty evidence URI, producer identity, verification method, and a recent integer verification timestamp. Gate-specific booleans are also required. Missing, stale, future-dated, unauthenticated, revoked/unknown, mismatched, or incomplete evidence blocks.

The adapter is responsible for authenticating the receipt before it sets `authenticated: true`; the evaluator only checks the declared contract. Do not wire raw GitHub API responses or user-authored JSON directly as trusted receipts.

## Gate matrix

| Gate | Accountable role | Minimum evidence / acceptance condition |
|---|---|---|
| `live_pr_state` | Release coordinator | Fresh metadata; PR open, draft, unmerged; valid current head SHA |
| `exact_head_ci` | CI owner | Completed successful required checks whose head SHA equals the current PR head |
| `effective_protection` | Authorized repository administrator | Authenticated effective settings readback; actual admin authorization |
| `reviewer_assignment` | Authorized repository administrator | Actual assignment; qualification and independence evidence |
| `independent_review` | Independent security reviewer | Review is independent, bound to current SHA, and findings are dispositioned |
| `remediation_retest` | Independent security reviewer | All findings independently retested and bound to current SHA |
| `trusted_provenance` | Trusted CI/provenance owner | Signature, issuer, repository, workflow, and artifact digest verified |
| `human_acceptance` | Authorized human approver | Authenticated acceptance, approver authorization, and matching manifest digest |
| `rx19_handoff` | RX-19 integration owner | Authenticated receipt, matching packet digest, recipient identity RX-19 |

The evaluator returns `READY_FOR_RX19_REVIEW` only when all nine gates pass. This means only that the supplied evidence meets the local contract and the packet is eligible for canonical review. It does not mean that RX-19 approved it. The returned `release_decision` remains `BLOCK` and `rx19_decision_evaluated` remains false; no release decision or external action is synthesized.

## Determinism and audit

- Gate ordering is fixed.
- Gate reasons are deduplicated and sorted.
- The report digest is SHA-256 over canonical JSON with sorted keys and compact separators.
- Evaluation time is injected, enabling reproducible tests.
- No files, network requests, repository mutations, or other external side effects occur.

## Test coverage

`tests/test_aigc_responsibility_closure.py` covers complete evidence, missing evidence, stale CI, stale receipt, wrong commit, unauthenticated receipt, manifest mismatch, invalid PR state, missing live snapshots, and deterministic digest output.

Run locally from the repository root:

```sh
PYTHONPATH=src python -m unittest discover -s tests -p 'test_aigc_responsibility_closure.py' -v
```

The CI result must be inspected for the exact PR head after this change. A passing unit suite is not a substitute for external admin/reviewer/approver actions, trusted producer verification, or RX-19's sole decision.

## Current release policy

- Preserve PR #330 as draft/open/unmerged.
- Any new commit invalidates the prior exact-head CI binding and any candidate-bound receipts.
- Never treat an HTTP 403, empty protection response, missing review, skipped attestation, or unavailable connector as a pass.
- Never fabricate identities, assignments, signatures, approvals, evidence digests, or receipt IDs.
- No privileged OIDC or attestation broadening to untrusted pull-request code to make a check green.
- RX-19 alone decides release.
