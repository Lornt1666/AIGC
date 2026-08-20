# AIGC Repository Migration Map

Status: evidence-backed convergence map. No deletion is authorized merely by appearing here.

## Classification rules

CANONICAL_KEEP; CANONICAL_REFACTOR; CANONICAL_MOVE; MERGE_DUPLICATE; SUPERSEDED_DELETE_CANDIDATE; HISTORICAL_EVIDENCE_KEEP; GENERATED_ARTIFACT_REMOVE; SECURITY_REVIEW_REQUIRED; UNKNOWN_REQUIRES_REVIEW.

Deletion requires a replacement where needed, migrated useful content, zero runtime/test/workflow/deployment references, no security/release/historical evidence requirement, and passing post-removal tests. Unknown means deletion_safe=false.

## Current-main and open-train mapping

| Surface | Classification | Canonical destination / role | Migration / deletion ruling |
|---|---|---|---|
| PR #176 canonical Colosseum architecture documents | CANONICAL_KEEP | docs/architecture | Product ontology and convergence contract. Preserve as canonical until superseded by a reviewed version. |
| PR #176 `src/colosseum` typed domain contracts | CANONICAL_KEEP | src/colosseum | New canonical compatibility target for EmployerVault, Opportunity, Engagement, WorkOrder, AgentCell, Swarm, Deliverable, Verification, WorkLedger, CapabilityEvidence and Compute Exchange contracts. Runtime adapters remain deferred. |
| PR #176 Colosseum / Compute Exchange schemas | CANONICAL_KEEP | schemas/colosseum + schemas/compute_exchange | Cross-language trust-boundary contracts for future Python/Swift/cloud implementations. |
| Current main Ω Mission OS connector kernel / activation framework | CANONICAL_REFACTOR | Trust/Governance + platform-policy/connector execution substrate | Preserve controls; map Mission/Quest vocabulary into canonical Engagement/WorkOrder/Task without weakening exact-SHA, approval, replay, rate or evidence controls. No deletion yet. |
| PR #170 governed Gemini opportunity-assessment release candidate | HISTORICAL_EVIDENCE_KEEP + CANONICAL_REFACTOR | Opportunity Intelligence + model/tool procurement + verification/evidence | Release evidence must remain reviewable. Reuse bounded Gemini controls; do not make Gemini the product ontology. No deletion. |
| PR #171 Canadian Cloud Operator skill | CANONICAL_REFACTOR | Trust/Governance + Compute Exchange jurisdiction policy | Preserve Canadian execution-policy work; Compute Exchange must support multiple admissible providers/resources rather than hard-code one provider globally. |
| PR #172 Québec Google Cloud foundation | CANONICAL_KEEP | Infrastructure implementation for an approved Compute Exchange route | Preserve Montréal plan-first infrastructure and truthful global-control-plane limitations. It is one execution venue, not the whole Compute Exchange. |
| PR #173 OMNI-FORGE domain kernel | CANONICAL_REFACTOR | omni_forge substrate | Preserve deterministic state, authorization, idempotency, budgets and evidence; future compatibility adapters should bind admitted OMNI-FORGE contracts to Employer/Engagement/WorkOrder/Swarm/Deliverable vocabulary. |
| PR #174 Diamond Protocol v2 / contract validation | SECURITY_REVIEW_REQUIRED | Trust/Governance validation substrate | Potentially valuable schema-hardening; reconcile naming and authority order before adoption. Do not delete. |
| PR #175 App Store readiness | CANONICAL_KEEP | app_store + iOS release governance | Preserve as release-readiness rail; update product identity from generic orchestration to AIGC digital workforce before final metadata. |
| PR #169 Evidence Plane contracts | CANONICAL_REFACTOR | Verification/Evidence + Reputation/Benchmark | Preserve metric/evidence semantics; align future metrics with accepted employer value, capability evidence and ComputeBenchmark observations. |
| PR #166 Policy Enforcement Layer | CANONICAL_KEEP | Trust/Security/Governance | Preserve fail-closed authority controls. |
| PR #152 / #145 older Gemini trains | HISTORICAL_EVIDENCE_KEEP / MERGE_DUPLICATE | archive/release evidence after PR #170 disposition | PR #170 reconstitutes much of this work. Do not delete until exact blob/reference/evidence analysis proves what is superseded. |
| PR #144 OMNARCHON/HLX² parameters | CANONICAL_REFACTOR | omni_forge planning/optimization substrate | Keep useful bounded optimization concepts; remove literal/competing ontology only after reference analysis. |
| PR #142 cloud advancement loop | MERGE_DUPLICATE / HISTORICAL_EVIDENCE_KEEP | operations/evidence | Reconcile with current completion loop/cloud foundation; do not delete while it carries historical evidence. |
| PR #129 canonical deployment/autonomy sequence | HISTORICAL_EVIDENCE_KEEP / CANONICAL_REFACTOR | operations + governance | Valuable runner diagnosis and authority separation. Sequence references may be stale. |
| PR #126 Actions remediation receipts | HISTORICAL_EVIDENCE_KEEP | CI/evidence governance | Preserve until Actions blocker resolved and evidence archived. |
| PR #125 inert Terraform evidence | CANONICAL_REFACTOR | infrastructure/evidence | Reconcile with PR #172 Terraform foundation. |
| PR #123 CI hardening | CANONICAL_KEEP / MERGE_DUPLICATE | CI exact-head/evidence | Preserve security principles; reconcile with newer exact-head workflow work. |
| PR #122 Jobs & Interviews cockpit | CANONICAL_REFACTOR | Opportunity + Engagement + future iOS command center | Valuable product precursor; map to Opportunity, EmployerVault, Engagement and WorkOrder contracts through compatibility adapters rather than deleting first. |
| PR #121 Cloud SQL staging gates | MERGE_DUPLICATE / HISTORICAL_EVIDENCE_KEEP | infra/gcp/quebec + authorization | Reconcile with PR #172; no deletion until dependency/reference comparison. |
| PR #79 Quest handoffs / Omega-X conductor | CANONICAL_REFACTOR | Colosseum Swarm Scheduler / WorkOrder orchestration | Strong precursor to SWARM orchestration. Migrate Quest/AgentHandoff semantics into WorkOrder/AgentCell/Swarm contracts rather than discard. |
| PR #75 PR graph / saturation gate | CANONICAL_KEEP / HISTORICAL_EVIDENCE_KEEP | repository governance | Preserve review saturation and dependency evidence while convergence is underway. |

## Immediate conclusion

No existing legacy file or open PR is presently proven safe to delete from the evidence available to this connector session. The repository contains substantial overlapping generations, but many carry security, CI, release or architectural evidence. PR #176 now provides the first canonical typed destination needed for compatibility migration and later reference-proven deletion.

## Target topology

New work should converge toward src/{opportunity,engagement,occupations,colosseum,compute_exchange,verification,evidence,business,employers,governance,omni_forge}, matching schemas/tests/config/docs domains. Existing paths move only after import/reference/workflow analysis and tests prove safety.
