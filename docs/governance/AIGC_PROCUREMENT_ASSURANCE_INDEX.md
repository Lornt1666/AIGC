# AIGC Procurement and Assurance Index

This index connects the current AIGC governance procurements into one reviewable documentation set.

## Included documents

- `programs/AIGC_EIAP_ASSURANCE_PROGRAM.md` — integrated engineering intelligence and assurance program.
- `standards/AIGC_ASSURANCE_SENSORIUM_STANDARD.md` — deterministic observation and nano-control mesh.
- `standards/AIGC_REVIEW_PACKET_STANDARD.md` — exact-head review packet requirements and decision workspace.
- `charters/AIGC_ENGINEERING_REVIEW_COUNCIL_CHARTER.md` — standing human review council and advisory-circle governance.
- `policies/AIGC_REVIEW_AUTHORITY_AND_EXTERNAL_ASSURANCE_POLICY.md` — review authority classes, solo-operator alternative assurance, external provider due diligence, and IP/confidentiality controls.
- `procedures/AIGC_ZERO_AMBIGUITY_PROCUREMENT_WORKFLOW.md` — five-phase procurement procedure.
- `procedures/AIGC_ASSURANCE_IMPLEMENTATION_CHECKLIST.md` — bounded implementation gates from PR #29 through production continuation.
- `procedures/AIGC_INDEPENDENT_REVIEWER_RECRUITMENT_AND_ONBOARDING_PACKET.md` — reviewer recruitment, screening, access, review, and revocation process.
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

These documents are proposed governance and implementation specifications. They do not prove runtime, staging, production, certification, compliance, or independent human review. Implementation requires bounded PRs, CI, review packets, the review path required by the applicable risk class, operator-controlled merge, rollback, and readiness evidence.

## Review authority statement

AIGC distinguishes automated verification, AI advisory review, operator ratification, independent external assurance, and independent human review. These events are never interchangeable.

For solo-operated, bounded, reversible, non-production changes, the proposed Review Authority Policy permits a clearly disclosed Solo-Operator Alternative Assurance Path. This path never creates or claims independent human review. Release-critical changes still require a distinct human reviewer.

## Current gating dependency

PR #29 remains the declared prerequisite for the ordered implementation train under the original strict-review path. The proposed Review Authority Policy also defines a transparent bootstrap alternative for PR #29: exact-head CI, strongest available advisory review, explicit operator risk acceptance, expected-head protected merge, and mandatory post-merge verification. Selecting that path changes the governance requirement; it does not fabricate historical independence.

## Shared invariants

- No completion claim without evidence.
- No consequential action without attributable authority.
- No implicit permit.
- No secrets in repository configuration or evidence packets.
- No direct write to `main`.
- No false independence or human-identity claim.
- No blocking finding averaged away.
- No production-ready claim while blocking capabilities remain.
- Every governed change preserves rollback and revision binding.
- Provider contracts never replace least-privilege technical controls.

## Next implementation order

```text
select PR #29 review path
→ satisfy the selected path without false claims
→ merge PR #29 with expected-head protection
→ verify main CI/readiness receipt
→ refresh and review PR #41
→ AEC-001 bounded implementation
→ EIAP shared assurance contracts
→ Assurance Sensorium v1
→ Review Packet Generator v1
→ Review Evidence Agent v1
→ Identity Kernel v1
→ Documentation Rendering Agent v1
→ staging, monitoring, recovery, connectors, and deployment
```

## Documentation-package review checklist

- [ ] terminology and hierarchy are consistent;
- [ ] human, operator, AI, and provider authorities are distinct;
- [ ] solo-operator alternative assurance is restricted and disclosed;
- [ ] provider IP/confidentiality controls are practical and do not overclaim enforceability;
- [ ] lifecycle and procurement gates fail closed;
- [ ] no certification or production maturity is claimed;
- [ ] implementation remains decomposed into bounded PRs;
- [ ] rollback and post-merge verification are mandatory;
- [ ] public-facing explanations remain understandable.
