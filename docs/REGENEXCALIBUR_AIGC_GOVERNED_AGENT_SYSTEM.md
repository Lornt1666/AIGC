# RegenExcalibur × AIGC — Governed Project Agent System

**Document ID:** RX-AIGC-AGENT-ARCH-001  
**Version:** 1.0.0  
**Status:** DESIGN BASELINE — NOT A PRODUCTION AUTHORIZATION  
**Project:** RegenExcalibur regenerative built-environment systems, governed through AIGC  
**Canonical software release authority:** AIGC Release Assurance Agent  
**Human accountable owner:** Project-designated RegenExcalibur owner  
**Default disposition:** BLOCK on missing, stale, unauthenticated, contradictory, or unreviewed evidence

## 1. Mission and separation of concerns

AIGC is the governed orchestration and evidence platform. RegenExcalibur is the engineering and product-development program. AIGC agents may research, model, draft, test, compare, and prepare decisions; they must not silently convert a concept into a fabrication instruction, permit submission, procurement commitment, public environmental claim, or software release.

Each agent has a versioned contract, narrow tool allowlist, input provenance, deterministic output schema, explicit failure states, audit events, and human approval boundaries. Agents may recommend; designated accountable people approve high-consequence decisions. The canonical AIGC Release Assurance Agent remains the sole authority for AIGC software release disposition.

## 2. Agent roster and authorities

| ID | Agent | Primary responsibility | Authority boundary |
|---|---|---|---|
| RX-00 | RegenExcalibur Program Governor | Maintain scope, milestones, dependencies, decision log, risks, and cross-agent handoffs | Coordinates; cannot approve its own deliverables or bypass domain reviewers |
| RX-01 | Requirements & Traceability Architect | Convert owner needs into versioned requirements, acceptance criteria, verification methods, and trace links | Cannot mark a requirement verified without linked evidence |
| RX-02 | Built-Environment Systems Architect | Maintain system context, interfaces, envelope/structure/MEP dependencies, and design alternatives | Concept/design assistance only; licensed professionals own regulated design |
| RX-03 | Materials & Fabrication Engineer | Track material candidates, compatibility, durability, repairability, manufacturing constraints, and test plans | No fabrication-ready claim without qualified engineering approval and verified drawings/BOM |
| RX-04 | Building Envelope & BIPV Integration Agent | Assess façade, weather barrier, thermal bridge, moisture, fire, electrical, serviceability, and BIPV integration interfaces | Cannot certify code compliance, electrical safety, or structural adequacy |
| RX-05 | Carbon & MRV Assurance Agent | Define baseline, system boundary, functional unit, lifecycle stages, uncertainty, monitoring, reporting, verification, and data lineage | No quantified carbon-removal/reduction claim without reproducible calculation and independent verification |
| RX-06 | Codes, Permits & Regulatory Research Agent | Research applicable jurisdictional codes, permits, standards, authorities having jurisdiction, and edition dates | Research only; never represents a regulator or issues legal/code approval |
| RX-07 | Safety, Hazard & Constructability Agent | Maintain hazard register, failure-mode analysis, safe-work interfaces, maintainability, and constructability reviews | Cannot waive hazards or substitute for competent safety review |
| RX-08 | Product Lifecycle & Circularity Agent | Evaluate repair, replacement, disassembly, reuse, recycling, end-of-life pathways, and embodied impacts | Claims require sourced evidence and declared assumptions |
| RX-09 | Supply Chain & Procurement Analyst | Compare vendors, lead times, certifications, country/source risks, cost confidence, and substitution controls | No purchase orders, commitments, or vendor onboarding without human authorization |
| RX-10 | Commercial & Finance Modeler | Maintain transparent CAPEX/OPEX, sensitivity, scenario, cash-flow, and unit-economics models | Estimates are not quotations, financing commitments, or guaranteed returns |
| RX-11 | Research & Evidence Librarian | Maintain source register, primary-source preference, publication dates, confidence, conflicts, and evidence freshness | Cannot treat search snippets, unsourced assertions, or agent consensus as proof |
| RX-12 | Digital Twin & Data Contract Architect | Define canonical project IDs, asset/component schemas, versioned interfaces, BIM/CAD references, telemetry, and data quality rules | Cannot mutate authoritative design records without approved change control |
| RX-13 | Test, Commissioning & Verification Planner | Build test matrices, mockups, commissioning steps, instrumentation plans, acceptance criteria, and failure retests | Cannot certify a test it did not independently observe or validate |
| RX-14 | Independent Design & Claims Reviewer | Challenge design assumptions, safety, code mapping, carbon claims, calculations, and evidence integrity | Must be organizationally independent of the authoring agent and disclose conflicts |
| RX-15 | Change-Control & Configuration Manager | Control baselines, revisions, approvals, impact analysis, supersession, and rollback | Cannot approve its own change or overwrite released baselines without authorization |
| RX-16 | AIGC Evidence & Provenance Verifier | Bind evidence to exact repository commit, workflow run, artifact digest, signer, predicate, and policy version | Evidence readiness only; cannot authorize a release |
| RX-17 | Security, Privacy & Tool-Permission Agent | Enforce least privilege, secret handling, tool allowlists, prompt-injection boundaries, threat modeling, and incident escalation | Cannot grant itself permissions or disable required controls |
| RX-18 | Audit & Retention Custodian | Record attributable, time-bounded events and verify independently administered retention and retrieval | A local log or hash chain alone is not proof of immutable independent retention |
| RX-19 | Release Assurance Agent | Evaluate the complete software release packet and return BLOCK or the policy-authorized release disposition | Sole AIGC software release authority; never self-certifies missing evidence |
| RX-20 | Human Decision & Acceptance Gate | Capture authenticated approval, approver authority, exact version/digest, scope, timestamp, and any conditions | Never fabricate acceptance or treat silence, CI success, or agent output as consent |

## 3. Shared agent contract

Every agent invocation MUST receive a TaskContract with:
- contract version, task ID, project ID, agent ID, agent version, and policy version;
- objective, scope, exclusions, acceptance criteria, risk tier, deadline, and resource budget;
- exact input references with content digests, source identity, observed time, and trust classification;
- allowed tools/actions and permitted side effects (default: none);
- required output schema, evidence requirements, and reviewer role;
- cancellation, timeout, retry, idempotency, and ambiguous-outcome rules.

Every agent MUST emit an AgentResult with:
- status: SUCCEEDED, PARTIAL, BLOCKED, FAILED, or UNKNOWN;
- summary, assumptions, limitations, risks, and open questions;
- versioned artifacts and SHA-256 digests, evidence references, citations, and test results;
- requirements-to-evidence trace links and unresolved findings;
- proposed next actions clearly separated from actions actually executed;
- side effects performed and matching audit event IDs;
- explicit approval-required and approval-status fields.

Unknown schema versions, missing provenance, policy mismatch, invalid signature, expired evidence, or contradictory critical evidence MUST fail closed.

## 4. Authority tiers

- R0 — Observe: read approved sources, inspect, summarize, classify.
- R1 — Draft: create proposals, models, plans, code, calculations, and candidate policies in isolated workspaces.
- R2 — Test: run bounded offline/sandbox tests and produce evidence; no production side effects.
- R3 — Controlled execution: only explicit allowlisted actions with scoped authorization, expiry, idempotency, pre-dispatch audit receipt, and rollback/compensation plan.
- R4 — Human-reserved decisions: regulated design acceptance, permit/legal attestations, fabrication release, procurement commitment, public environmental claims, production deployment, and final software release. Agents may assemble packets but cannot impersonate the authorized human or regulator.

Risk classification may raise controls, never silently lower them. Consequential actions require a separate policy decision and controller enforcement independent of the proposing agent.

## 5. Cross-agent workflow

1. Program Governor creates a scoped task and assigns a risk tier.
2. Requirements Architect defines acceptance criteria and traceability.
3. Research Librarian collects primary sources and marks uncertainty and freshness.
4. Domain agents develop alternatives and explicit assumptions.
5. Safety, Codes, Carbon/MRV, and Lifecycle agents perform mandatory domain reviews as applicable.
6. Test & Commissioning Planner creates testable acceptance evidence.
7. Independent Reviewer challenges the exact version and reports findings.
8. Change Control resolves findings and freezes a new immutable baseline.
9. Evidence Verifier validates artifact identity, provenance, and completeness.
10. Human Decision Gate captures authorized acceptance for the exact version.
11. For AIGC code changes, Release Assurance evaluates CI, security, provenance, audit, review, and acceptance; only the canonical release authority may decide the software release gate.

A changed input, source revision, drawing, calculation, dependency, policy, or artifact digest invalidates affected downstream approvals and requires impact analysis and revalidation.

## 6. RegenExcalibur-specific mandatory gates

### Engineering and fabrication
- Defined operating conditions, interfaces, load cases, design assumptions, tolerances, materials, installation/maintenance access, and failure modes.
- Applicable code/standard editions and jurisdiction reviewed by qualified personnel.
- Verified calculations, drawings, BOM, QA/inspection plan, prototype test results, and manufacturing change control before any fabrication-ready status.
- Fire, moisture, wind, structural, electrical, thermal, and occupant-safety issues evaluated where applicable.

### Carbon, capture, and environmental claims
- Declared baseline, functional unit, system boundary, lifecycle stages, counterfactual, additionality where relevant, uncertainty, permanence/leakage where relevant, and measurement plan.
- Separate gross capture, net removal/reduction, embodied emissions, energy penalty, and lifecycle emissions; do not conflate them.
- Versioned inputs and reproducible calculations; independent verification before public claims.
- If data is unavailable, label results as estimates or hypotheses and state the missing evidence.

### Commercial and delivery
- Estimates show currency, date, geography, source, exclusions, confidence, and sensitivity.
- Vendor claims, certifications, lead times, and substitutions are verified against primary evidence.
- Procurement, contracts, financing, permits, external communications, and site work require explicit authorized human approval.

## 7. Security, audit, and operational controls

- Use separate service identities per agent and environment; no shared unrestricted credentials.
- Tools are allowlisted by action ID and schema; no arbitrary shell, network, file, or repository write access by default.
- Treat documents, web pages, model outputs, code comments, and uploaded files as untrusted data, not policy instructions.
- Secrets are injected at runtime from an approved secret manager and never logged or committed.
- Record task, policy, model/version, input/output digests, tool calls, approvals, retries, failures, and side effects to a separately administered audit system.
- Use idempotency keys and explicit UNKNOWN outcomes for ambiguous dispatch; never retry a non-idempotent consequential action blindly.
- Require retention, access review, tamper detection, restore tests, incident response, and audit export.
- Agent consensus is not independent review. Reviewers must not be the author, approver, or sole operator of the same evidence path.

## 8. MVP++ implementation sequence

Phase 0 — Inventory and policy: inventory current AIGC services, contracts, repository rules, available sources, data owners, and project risks. Freeze role boundaries and evidence schemas.

Phase 1 — Read-only MVP: implement Program Governor, Requirements/Traceability, Research Librarian, Evidence Verifier, Change Control, and Human Acceptance Gate using fixtures and offline tests.

Phase 2 — Domain workbenches: add Carbon/MRV, Codes/Permits, Envelope/BIPV, Materials/Fabrication, Lifecycle, and Safety agents with source-cited outputs and explicit uncertainty.

Phase 3 — Verification: add independent test planning, threat modeling, adversarial tests, schema validation, provenance verification, audit durability tests, and fault injection.

Phase 4 — Controlled integrations: connect approved repositories, BIM/document stores, telemetry, or vendor systems through isolated adapters and narrowly scoped service identities. Start read-only; enable writes only after separate authorization and rollback testing.

Phase 5 — Independent acceptance: obtain a qualified independent review, remediate findings, validate retained evidence, and record explicit human acceptance against exact digests. Keep production and fabrication gates closed until their respective acceptance criteria pass.

## 9. Acceptance checklist

- [ ] All agents have stable IDs, owners, versioned input/output schemas, risk tier, and explicit authority boundaries.
- [ ] Dependency graph is acyclic or has explicit bounded feedback loops and iteration limits.
- [ ] Every output has provenance, assumptions, limitations, evidence references, and reproducible digests.
- [ ] Policy tests cover missing, stale, forged, contradictory, replayed, revoked, and wrong-subject evidence.
- [ ] Tool permissions are least-privilege and independently enforced outside the agent process.
- [ ] Consequential actions require durable pre-dispatch audit receipts and idempotency controls.
- [ ] Independent reviewers are identity-authenticated, conflict-checked, and bound to the exact artifact digest.
- [ ] Human acceptance is authenticated and version-bound.
- [ ] CI passes on the exact commit; signed provenance is independently verified; retained artifacts are retrievable.
- [ ] Domain-specific engineering, code, safety, carbon/MRV, and commercial claims are approved by competent human authorities where required.

**Release posture:** DESIGN BASELINE ONLY. This document defines the agent architecture and acceptance criteria; it does not claim that these agents have all been implemented, connected to live services, independently reviewed, or authorized for production.
