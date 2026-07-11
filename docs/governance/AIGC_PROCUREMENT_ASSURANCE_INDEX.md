# AIGC Procurement and Assurance Index

This index connects the current AIGC governance procurements into one reviewable documentation set.

## Included documents

- `programs/AIGC_EIAP_ASSURANCE_PROGRAM.md` — integrated engineering intelligence and assurance program.
- `standards/AIGC_ASSURANCE_SENSORIUM_STANDARD.md` — deterministic observation and nano-control mesh.
- `standards/AIGC_REVIEW_PACKET_STANDARD.md` — permanent revision-bound reviewer workspace standard.
- `charters/AIGC_ENGINEERING_REVIEW_COUNCIL_CHARTER.md` — standing human review and external advisory structure.
- `procedures/AIGC_ZERO_AMBIGUITY_PROCUREMENT_WORKFLOW.md` — five-phase procurement procedure.
- `procedures/AIGC_ASSURANCE_IMPLEMENTATION_CHECKLIST.md` — bounded task sequence from PR #29 through production continuation.
- `programs/AIGC_UPEP_001.md` — universal lifecycle from intent through retirement.

## Related repository work

- PR #29 — Production Readiness Ledger
- Issue #30 — Identity, Scope and Authorization Decision Kernel
- Issue #31 — AEC-001 Constitution and executable governance graph
- Issue #32 — PR Review Evidence Agent
- Issue #33 — Sovereign Documentation Rendering Agent
- Issue #34 — Constitutional Control Plane execution graph
- Issue #35 — EIAP program
- Issue #36 — Permanent Review Packet Generator
- Issue #37 — Engineering Review Council
- Issue #38 — Assurance Sensorium
- Issue #39 — Zero-Ambiguity Procurement Workflow
- Issue #40 — UPEP-001

## Authority and maturity statement

These documents are proposed governance and implementation specifications. They do not prove runtime, staging, production, certification, compliance, or independent review. Implementation requires separate bounded PRs, CI, review packets, required independent review, operator-controlled merge, rollback, and readiness evidence.

## Current gating dependency

PR #29 remains the declared prerequisite for the ordered implementation train. This documentation PR may be reviewed independently, but it must not be used to represent PR #29 as independently approved or merged.

## Shared invariants

- No completion claim without evidence.
- No consequential action without attributable authority.
- No implicit permit.
- No secrets in repository configuration or evidence packets.
- No direct write to `main`.
- No self-approval or false independence claim.
- No blocking finding averaged away.
- No production-ready claim while blocking capabilities remain.
- Every governed change preserves rollback and revision binding.
- No review packet remains valid after its bound revision changes.
- No council role permits review beyond declared competence.
- No procurement phase is skipped or retroactively justified.

## Next implementation order

```text
PR #29 independent review and merge
→ verify main CI/readiness receipt
→ AEC-001 bounded implementation
→ EIAP shared assurance contracts
→ Assurance Sensorium v1
→ Review Packet Generator v1
→ Review Evidence Agent v1
→ Engineering Review Council onboarding
→ Identity Kernel v1
→ Documentation Rendering Agent v1
→ UPEP-001 initial implementation
→ Review Knowledge Graph
→ staging, monitoring, recovery, connectors, and deployment
```

## Review checklist for this documentation package

- [ ] Terminology is consistent across all documents.
- [ ] Human authority and AI advisory functions remain distinct.
- [ ] PR #29 is not represented as independently approved or merged.
- [ ] Fail-closed rules are consistent.
- [ ] Shared primitives are reused rather than duplicated.
- [ ] Review Council independence and conflict rules are explicit.
- [ ] Review Packet Generator outputs and staleness rules are complete.
- [ ] The implementation checklist remains bounded and sequential.
- [ ] No unsupported certification, compliance, staging, or production claim appears.
- [ ] All future implementations remain separate reviewed PRs.
