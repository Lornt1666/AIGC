# AIGC Permanent Review Packet Standard

## Status

Proposed governance standard. This document defines a review-packet contract; it does not implement runtime generation, approve changes, or satisfy independent human review.

## Purpose

Every governed AIGC pull request shall be reviewable without forcing the reviewer to reverse-engineer the repository. A review packet must present the exact proposed change, its evidence, risks, unknowns, rollback path, and required human decision in one revision-bound workspace.

## Mandatory outputs

A conforming generator produces:

- `review_packet.json`
- `review_packet.md`
- `review_decision_sheet.json`
- `review_packet_receipt.json`

All outputs bind to repository, PR number, base SHA, head SHA, policy versions, generator version, and generation timestamp.

## Required sections

1. Executive Summary
2. Scope and Intent
3. Constitutional Traceability
4. Architecture Diff
5. Contract Diff
6. Schema Diff
7. Implementation Diff
8. Testing and Regression Diff
9. Security Diff
10. Privacy Diff
11. Accessibility Diff
12. Identity and Authorization Impact
13. Supply-Chain and Provenance Impact
14. Readiness Impact
15. Operations and Recovery Impact
16. Documentation Impact
17. Risks, Assumptions, and Unknowns
18. Rollback Plan
19. Questions for Reviewer
20. Suggested Review Time
21. Reviewer Decision Sheet
22. Evidence Appendix

## State machine

```text
REQUESTED
→ SOURCE_BOUND
→ EVIDENCE_COLLECTED
→ EVIDENCE_VALIDATED
→ DIFFS_CLASSIFIED
→ DOMAIN_ANALYSES_COMPLETE
→ PACKET_RENDERED
→ QUALITY_GATES_PASSED | BLOCKED
→ READY_FOR_HUMAN_REVIEW
→ STALE_ON_HEAD_CHANGE
```

## Fail-closed rules

- A head-SHA mismatch makes the packet stale.
- Missing mandatory evidence yields `INSUFFICIENT_EVIDENCE`.
- Blocking findings cannot be hidden by scores or summaries.
- Structural evidence cannot be described as runtime or production proof.
- Operator ratification cannot be described as independent review.
- Unsupported compliance, certification, or production claims are blocking.
- Secret exposure is blocking.
- Unknown schema, policy, or generator versions fail closed.

## Review-time estimate

The estimate must be based on changed files, changed lines, schema and contract changes, security/privacy-sensitive paths, migrations, findings, test delta, documentation quality, and unresolved assumptions. It must include a confidence level and basis. False precision is prohibited.

## Decision sheet

The reviewer receives:

- exact reviewed head SHA;
- mandatory review domains;
- unresolved findings;
- questions requiring judgment;
- checklist completion state;
- options: `APPROVE`, `REQUEST_CHANGES`, `COMMENT`, `ABSTAIN_INSUFFICIENT_EXPERTISE`;
- confirmation that the reviewer personally inspected the evidence;
- expiry and staleness notice.

## Quality gates

A packet is review-ready only when:

- all mandatory sections exist;
- evidence references resolve;
- security and privacy scans pass;
- unknowns are explicit;
- rollback is actionable;
- plain-language and technical views agree;
- independent-review status is represented truthfully;
- the packet is bound to the current head.

## Negative tests

Required tests include head drift, missing CI, unresolved threads, author-as-independent-reviewer, omitted schema change, unidentified breaking contract, secret leakage, unsupported readiness claims, missing rollback, unsupported time estimate, and stale packet treated as current.

## Initial implementation boundary

Version 1 supports one AIGC repository and one GitHub pull request, producing Markdown and JSON only. It does not approve, merge, publish, deploy, or change branch protection.
