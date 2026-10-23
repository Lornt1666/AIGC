# AIGC MVP Master Documentation — Index and Reading Order

**Business/project identity:** RegenExcalibur  
**Owner-designated principal:** Justice Gray Maciocha  
**Product:** Artificial Intelligence Gladiator Coliseum (AIGC)  
**Release authority:** RX-19 under current governance  
**Status:** Documentation baseline proposed for review; not production certification.

## Read in this order

1. [MVP Master Specification](AIGC_MVP_MASTER_SPECIFICATION.md) — what AIGC is supposed to do, system boundaries, phases, target architecture, data flows, persistence, security, observability, and acceptance rules.
2. [Control-to-Evidence Traceability Standard](AIGC_CONTROL_TO_EVIDENCE_TRACEABILITY_STANDARD.md) — the normative chain from requirements to controls, implementation, tests, operational evidence, and authorized acceptance; includes system ordering, architecture trade-offs, required controls, failure modes, and release gates.
3. [Wiring and Interface Registry](AIGC_WIRING_AND_INTERFACE_REGISTRY.md) — 45 defined logical wires with producer/consumer, purpose, failure behavior, contract expectations, component responsibilities, agent roles, and unknowns requiring verification.
4. [Implementation Audit and Certification Dossier](AIGC_IMPLEMENTATION_AUDIT_AND_CERTIFICATION_DOSSIER.md) — candidate-specific source/CI findings, status for each of the 45 wires, blocking defects, remediation order, and the evidence required before a conformity certificate can be issued. Current disposition: NOT CERTIFIED / BLOCKED.
5. [Verification and Production Acceptance Plan](AIGC_VERIFICATION_AND_PRODUCTION_ACCEPTANCE_PLAN.md) — test layers, negative tests, fault-injection matrix, evidence model, release gates, and candidate-freshness rules.
6. [Operations, Security, and Recovery Runbook](AIGC_OPERATIONS_SECURITY_AND_RECOVERY_RUNBOOK.md) — safe local validation, staging deployment, emergency stop, queue handling, incident response, backup/recovery, and release closure operations.
7. [Operator Responsibility and Authorized Use Acknowledgment](AIGC_OPERATOR_RESPONSIBILITY_AND_AUTHORIZED_USE_ACKNOWLEDGMENT.md) — a draft operator-accountability and task-authorization record; not a blanket liability waiver and not legally adopted until reviewed by qualified counsel.
8. [Documentation Governance and Enforcement Agents](AIGC_DOCUMENTATION_GOVERNANCE_AND_ENFORCEMENT_AGENTS.md) — DOC-GATE-01, traceability, authorization, and evidence-gate roles, boundaries, and acceptance tests.
9. [Governance and System Charter](../AIGC_GOVERNANCE_AND_SYSTEM_CHARTER.md) — identity, authority hierarchy, agent role boundaries, governance, and change control.
10. [Production Closure Acceptance Matrix](../PRODUCTION_CLOSURE_ACCEPTANCE_MATRIX.md) — current closure gate matrix and evidence invariants.
11. [Repository README](../../README.md) — current command surface and documented phase behavior.

## How to use the master documents

- Treat the master specification as the design baseline and repository code/configuration as the current implementation source of truth.
- Treat the wiring registry as a checklist of interfaces to inspect and test, not as evidence every wire exists.
- Treat the traceability standard as the required chain from each normative requirement to an enforced control, implementation reference, verification, retained evidence, and acceptance criterion.
- Treat the implementation audit as a time-bound assessment of one candidate. It is not a certificate and must be refreshed after relevant changes.
- For every wire and control, assign an implementation status: `IMPLEMENTED_AND_TESTED`, `IMPLEMENTED_UNVERIFIED`, `PARTIAL`, `SPEC_ONLY`, `DISABLED`, or `BLOCKED`.
- Do not enable a spec-only agent or adapter because its role is documented.
- Record each discrepancy between intended behavior and observed implementation with exact file/line, candidate SHA, severity, owner, test, and disposition.
- Update these documents alongside behavior-changing code and contracts.
- CI invokes `scripts/enforce_master_docs.py` as DOC-GATE-01. Its structural checks are a documentation quality gate, not legal review, source-code conformity proof, or production certification; its current-head workflow must pass before this CI integration is considered verified.
- The operator acknowledgment is a draft. Do not represent it as an executed contract or blanket transfer of all legal responsibility; obtain qualified legal review and valid, task-specific assent.
- Any release evidence must refer to the exact candidate SHA and canonical evidence digest. A newer commit invalidates evidence that is not explicitly rebound to it.

## Current known boundaries

- Phase 2 and Phase 13 real-data replay are intended read-only.
- Phase 3 is assessment-only; Phase 4 drafts proposals; Phase 5 prepares scoped human approval; Phase 6 only processes eligible approved packets; Phase 7 drafts internal audit packets; Phase 8 proposes evolution changes requiring operator approval.
- Secret retrieval is disabled by default; the repository must store references rather than secret values.
- Static AST screening is not a sandbox and does not authorize code execution.
- PostgreSQL, Redis Streams, Qdrant, production telemetry, cryptographic permit verification, and external adapters must be verified in the actual checked-out implementation before they are claimed as integrated.
- The current candidate's canonical CI stage failed at redaction in run #4591; do not claim the complete workflow passed.
- AIGC is not production-authorized or certified by these documents.
