# AIGC Nexus V1 Convergence Inventory

Status: ACTIVE_INTEGRATION
Integration branch: `release/aigc-nexus-v1`
Contract: `AIGC_INTEGRATION_CONTRACT_V1`

## Purpose

Replace microscopic PR-by-PR product construction with one governed integration train. Existing work is classified by reusable capability, not blindly merged by branch history.

Classification vocabulary:

- `ABSORB` — reconstitute useful implementation/contracts into Nexus V1.
- `REUSE` — consume existing mainline capability directly.
- `SUPERSEDE` — preserve historical evidence but replace architecture/implementation with Nexus V1 contract.
- `ARCHIVE` — retain as historical evidence/reference; no active integration dependency.
- `BLOCK` — do not integrate until external/technical conditions are satisfied.

## Open-train classification

| PR | Capability | Nexus V1 disposition | Rationale |
|---|---|---|---|
| #178 | Epistemic contracts / canonical hashing | ABSORBED | Nexus branch is based on validated EPI-01 lineage. |
| #179 | Default-deny epistemic ToolBroker | ABSORBED | Nexus branch includes validated EPI-02 lineage. No live dispatch. |
| #180 | Deterministic Verifier | ABSORBED | Nexus branch includes validated EPI-03 lineage. |
| #177 | Colosseum planning/orchestration kernel | ABSORB_SELECTIVELY | Reuse WorkOrder/DoD/DAG/scheduler/verification/compute planning concepts behind V1 contracts; avoid competing authority/state models. |
| #173 | OMNI-FORGE deterministic domain kernel | ABSORB_SELECTIVELY | Reuse graph validation, bounded budgets, exact-bound authorization/evidence patterns where compatible. Nexus contract supersedes competing state semantics. |
| #169 | Evidence Plane contracts | ABSORB_SELECTIVELY | Metric/evidence/lineage contracts are valuable; Evidence remains non-authorizing. |
| #166 | Policy Enforcement Layer | ABSORB_SELECTIVELY | Preserve fail-closed policy/security invariants; GovernanceDecision becomes Nexus promotion envelope. |
| #170 | Governed Gemini release candidate | ABSORB_SELECTIVELY | Reuse provider isolation, emergency stop, idempotency, rate/budget, evidence and judge-read patterns. No live Gemini authority is inherited. |
| #172 | Quebec GCP foundation | BLOCK_FOR_RUNTIME / ABSORB_DESIGN | Reuse Canadian-region/IAM/budget/data-residency design after Nexus runtime is integrated; no Terraform apply or cloud mutation now. |
| #171 | Canadian cloud operator skill | ARCHIVE_REFERENCE | Useful operating policy; not a runtime dependency for Nexus V1 brain/dashboard. |
| #175 | App Store readiness | DEFER | Product-release surface after Nexus web/runtime integration. |
| #174 | Diamond/schema hardening | ABSORB_SELECTIVELY | Schema-validator hardening is useful; architectural roadmap is subordinate to frozen Nexus contract. |
| #152/#145 | Earlier Gemini/evidence trains | SUPERSEDE_BY_170 | Preserve historical evidence; use the later reconciled release-candidate controls. |
| #142 | Governed cloud advancement loop | ABSORB_SELECTIVELY | Reuse append-only/idempotency/recovery ideas; Nexus reconciliation protocol supersedes competing transition semantics. |
| #129/#126/#125/#123/#122/#121 | Historical CI/cloud/cockpit trains | ARCHIVE_OR_SELECTIVE_REUSE | Mainline and later trains supersede much of their coordination logic. Extract only capabilities still absent after inventory. |
| #79 | Quest handoffs / Agent Registry | ABSORB_SELECTIVELY | Strong precursor for dynamic specialist registry and internal handoffs; adapt to WorkOrder/ContextEnvelope/ArtifactState contracts. |
| #75/#74 | Historical PR graph/CI hardening | ARCHIVE_OR_SELECTIVE_REUSE | Preserve evidence and any still-missing CI invariants; do not recreate review-train saturation as product architecture. |

## Mainline capability families to preserve

- AEC/governance constitutional ordering.
- exact-head CI and canonical validation runner.
- redaction and secret scanning.
- existing identity/scope/authorization controls.
- external-action gateway default-deny law.
- evidence and readiness truthfulness rules.
- Terraform inert-plan validation.
- Cloud Run / Cloud SQL planning assets.
- current application/cockpit surfaces where compatible.

## Nexus V1 workstreams

### A. Integrated Brain

- frozen integration contracts;
- deterministic state reducer;
- optimistic concurrency control;
- GovernanceDecision and ExecutionPermit contracts;
- dry-run governance orchestrator;
- dynamic specialist registry;
- no consequential execution.

### B. Nexus Dashboard

- system health;
- run graph;
- WorkOrder view;
- ArtifactState/ChangeSet diff view;
- Verifier findings;
- governance approval console;
- execution/evidence ledger;
- memory/goal/assumption explorer;
- emergency-stop visibility.

### C. Memory & Evidence

- ContextEnvelope projections;
- episodic/semantic memory adapters behind interfaces;
- evidence references and immutable receipts;
- claim supersession and reconciliation history;
- no memory item grants authority.

### D. Controlled Capability Plane

- ToolBroker effect classes;
- read-only capability policies first;
- credential broker interface only;
- operation-granular receipts;
- partial/indeterminate reconciliation;
- live write adapters deferred until separate authorization.

### E. Infrastructure / Release

- local container composition;
- CI integration tests;
- deterministic replay tests;
- dashboard smoke tests;
- GCP plan-only integration;
- one Nexus V1 release candidate and one final governed PR to `main`.

## Immediate convergence rule

Do not merge historical PRs wholesale into the release branch merely because they contain useful work. Reconstitute compatible capabilities against `AIGC_INTEGRATION_CONTRACT_V1`, preserve provenance in commit/decision records, and reject duplicate authorities or competing canonical state machines.

## Authority state

`direct_main_write=false`
`automatic_merge=false`
`production_activation=false`
`cloud_mutation=false`
`live_model_call=false`
`external_message=false`
`financial_action=false`
`credential_material_in_permit=false`
